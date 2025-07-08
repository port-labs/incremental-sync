import asyncio

from loguru import logger

from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.settings import ResourceGroupTagFilters, app_settings


def build_rg_tag_filter_clause_for_containers(filters: ResourceGroupTagFilters) -> str:
    """Build KQL where clause for resource container tag filtering with include/exclude logic."""
    if not filters.has_filters():
        return ""

    conditions: list[str] = []

    # Build include conditions (AND logic within include)
    if filters.include:
        include_conditions = []
        for key, value in filters.include.items():
            escaped_key = key.replace("'", "''")
            escaped_value = value.replace("'", "''")
            include_conditions.append(
                f"tostring(tags['{escaped_key}']) =~ '{escaped_value}'"
            )

        if include_conditions:
            include_clause = " and ".join(include_conditions)
            conditions.append(f"({include_clause})")

    # Build exclude conditions (OR logic within exclude, then NOT the whole thing)
    if filters.exclude:
        exclude_conditions = []
        for key, value in filters.exclude.items():
            escaped_key = key.replace("'", "''")
            escaped_value = value.replace("'", "''")
            exclude_conditions.append(
                f"tostring(tags['{escaped_key}']) =~ '{escaped_value}'"
            )

        if exclude_conditions:
            exclude_clause = " or ".join(exclude_conditions)
            conditions.append(f"not ({exclude_clause})")

    if not conditions:
        return ""

    # Combine include and exclude with AND logic
    combined_condition = " and ".join(conditions)
    return f"| where {combined_condition}"


def build_incremental_container_query() -> str:
    # Get resource group tag filters
    rg_tag_filters = app_settings.get_resource_group_tag_filters()
    rg_tag_filter_clause = build_rg_tag_filter_clause_for_containers(rg_tag_filters)

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
    rg_tag_filter_clause = build_rg_tag_filter_clause_for_containers(rg_tag_filters)

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
        if rg_tag_filters.has_filters():
            filter_description = []
            if rg_tag_filters.include:
                filter_description.append(
                    f"including containers with tags: {rg_tag_filters.include}"
                )
            if rg_tag_filters.exclude:
                filter_description.append(
                    f"excluding containers with tags: {rg_tag_filters.exclude}"
                )

            logger.info(
                f"Resource container filtering enabled: {', '.join(filter_description)}"
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
