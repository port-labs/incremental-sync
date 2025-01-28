import asyncio

from loguru import logger

from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.settings import app_settings


INCREMENTAL_QUERY: str = f"""
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
| project  subscriptionId, resourceGroup, resourceId , sourceResourceId, name, tags, type, location, changeType, changeTime
| order by changeTime asc
"""

FULL_SYNC_QUERY: str = f"""
resourcecontainers 
   | extend resourceId=tolower(id) 
   | project resourceId, type, name, location, tags, subscriptionId, resourceGroup
"""

class ResourceContainers:

    def __init__(self, azure_client: AzureClient, port_client: PortClient):
        self.azure_client = azure_client
        self.port_client = port_client

    async def sync_full(
        self,
        subscriptions: list[str],
    ) -> None:
        logger.info(
            "Running query for subscription batch with "
            f"{len(subscriptions)} subscriptions"
        )

        async for items in self.azure_client.run_query(
            FULL_SYNC_QUERY,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resource containers")
            if not items:
                logger.info("No resources found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(self.port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="upsert",
                    type="resourceContainer",
                ))
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
            INCREMENTAL_QUERY,
            subscriptions,
        ):
            logger.info(f"Received batch of {len(items)} resources containers operations")
            if not items:
                logger.info("No changes found in this batch")
                continue
            tasks = []
            for item in items:
                tasks.append(self.port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="upsert" if item["changeType"] != "Delete" else "delete",
                    type="resourceContainer",
                ))
                if len(tasks) == 100:
                    await asyncio.gather(*tasks)
                    tasks = []
            await asyncio.gather(*tasks)