import asyncio
from loguru import logger

from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.settings import app_settings

def build_incremental_query(resource_types: list[str] | None = None) -> str:
    filter_clause = ""
    if resource_types:
        resource_types_filter = " or ".join([f"type == '{rt.lower()}'" for rt in resource_types])
        filter_clause = f"| where {resource_types_filter}"

    query = f"""
    resourcechanges 
    | extend changeTime=todatetime(properties.changeAttributes.timestamp)
    | extend targetResourceId=tostring(properties.targetResourceId)
    | extend changeType=tostring(properties.changeType)
    | extend changedProperties=properties.changes
    | project-away tags, name, type
    | extend type=tostring(properties.targetResourceType)
    | extend changeCount=properties.changeAttributes.changesCount 
    | extend resourceId=tolower(targetResourceId) 
    | where changeTime > ago({app_settings.CHANGE_WINDOW_MINUTES}m)
    {filter_clause}
    | summarize arg_max(changeTime, *) by resourceId
    | join kind=leftouter ( 
        resources 
        | extend sourceResourceId=tolower(id) 
        | project sourceResourceId, name, location, tags, subscriptionId, resourceGroup 
        | extend resourceGroup=tolower(resourceGroup)
    ) on $left.resourceId == $right.sourceResourceId 
    | project subscriptionId, resourceGroup, resourceId , sourceResourceId, name, tags, type, location, changeType, changeTime, changedProperties
    | order by changeTime asc
    """

    return query

def build_full_sync_query(resource_types: list[str] | None = None) -> str:
    filter_clause = ""
    if resource_types:
        resource_types_filter = " or ".join([f"type == '{rt}'" for rt in resource_types])
        filter_clause = f"| where {resource_types_filter}"

    query = f"""
    resources
    | extend resourceId=tolower(id)
    | project resourceId, type, name, location, tags, subscriptionId, resourceGroup
    | extend resourceGroup=tolower(resourceGroup)
    | extend type=tolower(type)
    {filter_clause}
    """

    return query

class Resources:
    def __init__(self, azure_client: AzureClient, port_client: PortClient):
        self.azure_client = azure_client
        self.port_client = port_client

    async def sync_full(
        self,
        subscriptions: list[str],
        resource_types: list[str] | None = None,
    ) -> None:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            build_full_sync_query(resource_types),
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources")
            if not items:
                logger.info("No resources found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(self.port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="upsert",
                    type="resource",
                ))
                if len(tasks) == 100:
                    await asyncio.gather(*tasks)
                    tasks = []
            await asyncio.gather(*tasks)

    async def sync_incremental(
        self,
        subscriptions: list[str],
        resource_types: list[str] | None = None,
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
            build_incremental_query(resource_types),
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resource operations")
            if not items:
                logger.info("No changes found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(self.port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="upsert" if item["changeType"] != "Delete" else "delete",
                    type="resource",
                ))
                if len(tasks) == 100:
                    await asyncio.gather(*tasks)
                    tasks = []
            await asyncio.gather(*tasks)