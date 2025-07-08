import asyncio
from typing import Dict

from loguru import logger

from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.settings import app_settings


def build_rg_tag_filter_clause_for_containers(
    tag_filters: Dict[str, str] | None, exclude: bool = False
) -> str:
    """Build KQL where clause for resource container tag filtering."""
    if not tag_filters:
        return ""

    conditions = []
    for key, value in tag_filters.items():
        # Escape quotes in tag values and handle case-insensitive comparison
        escaped_key = key.replace("'", "''")
        escaped_value = value.replace("'", "''")
        conditions.append(f"tostring(tags['{escaped_key}']) =~ '{escaped_value}'")

    if not conditions:
        return ""

    combined_condition = " and ".join(conditions)

    if exclude:
        return f"| where not ({combined_condition})"
    else:
        return f"| where {combined_condition}"


def build_incremental_container_query() -> str:
    # Get resource group tag filters
    rg_tag_filters = app_settings.get_resource_group_tag_filters()
    rg_tag_filter_clause = build_rg_tag_filter_clause_for_containers(
        rg_tag_filters, app_settings.EXCLUDE_RESOURCES_BY_RG_TAGS
    )

    query = f"""
    resourcecontainerchanges
    | extend changeTime = todatetime(properties.changeAttributes.timestamp)
    | extend resourceType = tostring(properties.targetResourceType) 
    | extend resourceId = tolower(properties.targetResourceId) 
    | extend changeType = tostring(properties.changeType)
    | extend changes = parse_json(properties.changes)
    | extend changeAttributes = parse_json(properties.changeAttributes)
    | project-away tags, name, type
    | where changeTime > ago({app_settings.CHANGE_WINDOW_MINUTES}m)
    | summarize arg_max(changeTime, *) by resourceId
    | join kind=leftouter ( 
        resourcecontainers 
        | extend sourceResourceId=tolower(id) 
        | project sourceResourceId, type, name, location, tags, subscriptionId, resourceGroup 
    ) on $left.resourceId == $right.sourceResourceId 
    {rg_tag_filter_clause}
    | project  subscriptionId, resourceGroup, resourceId , sourceResourceId, name, tags, type, location, changeType, changeTime
    | order by changeTime asc
    """
    return query


def build_full_sync_container_query() -> str:
    # Get resource group tag filters
    rg_tag_filters = app_settings.get_resource_group_tag_filters()
    rg_tag_filter_clause = build_rg_tag_filter_clause_for_containers(
        rg_tag_filters, app_settings.EXCLUDE_RESOURCES_BY_RG_TAGS
    )

    query = f"""
    resourcecontainers 
    | extend resourceId=tolower(id) 
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    {rg_tag_filter_clause}
    """
    return query


class ResourceContainers:
    def __init__(self, azure_client: AzureClient, port_client: PortClient):
        self.azure_client = azure_client
        self.port_client = port_client

        # Log resource group tag filtering configuration
        rg_tag_filters = app_settings.get_resource_group_tag_filters()
        if rg_tag_filters:
            action = (
                "excluding"
                if app_settings.EXCLUDE_RESOURCES_BY_RG_TAGS
                else "including"
            )
            logger.info(
                f"Resource container filtering enabled: {action} containers based on resource group tags: {rg_tag_filters}"
            )

    async def sync_full(
        self,
        subscriptions: list[str],
    ) -> None:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            build_full_sync_container_query(),
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resource containers")
            if not items:
                logger.info("No resources found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(
                    self.port_client.send_webhook_data(
                        data=item,
                        id=item["resourceId"],
                        operation="upsert",
                        type="resourceContainer",
                    )
                )
                if len(tasks) == 100:
                    await asyncio.gather(*tasks)
                    tasks = []
            await asyncio.gather(*tasks)

    async def sync_incremental(
        self,
        subscriptions: list[str],
    ) -> None:
        """
        Processes the subscriptions in batches and runs the query
        to retrieve the changes.
        The changes are then processed into upsert and delete tasks.
        """
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            build_incremental_container_query(),
            subscriptions,
        ):
            logger.info(
                f"Received batch of {len(items)} resources containers operations"
            )
            if not items:
                logger.info("No changes found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(
                    self.port_client.send_webhook_data(
                        data=item,
                        id=item["resourceId"],
                        operation=(
                            "upsert" if item["changeType"] != "Delete" else "delete"
                        ),
                        type="resourceContainer",
                    )
                )
                if len(tasks) == 100:
                    await asyncio.gather(*tasks)
                    tasks = []
            await asyncio.gather(*tasks)
