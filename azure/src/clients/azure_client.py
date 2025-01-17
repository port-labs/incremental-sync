from typing import Any, AsyncIterable

from loguru import logger

from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resourcegraph.aio import ResourceGraphClient  # type: ignore
from azure.mgmt.resourcegraph.models import QueryRequest  # type: ignore

# from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription.aio import SubscriptionClient
from azure.mgmt.subscription.models._models_py3 import Subscription


class AzureClient:
    def __init__(self) -> None:
        self.subs_client = SubscriptionClient(DefaultAzureCredential())
        self.resource_g_client = ResourceGraphClient(DefaultAzureCredential())

    async def get_all_subscriptions(self) -> AsyncIterable[Subscription]:
        logger.info("Getting all Azure subscriptions")
        async for sub in self.subs_client.subscriptions.list():
            yield sub

    async def run_query(
        self, query: str, subscriptions: list[str]
    ) -> list[dict[str, Any]]:
        logger.info("Running query")
        query = QueryRequest(subscriptions=subscriptions, query=query)
        response: list[
            dict[str, Any]
        ] = await self.resource_g_client.resources(query).data
        logger.info("Query ran with response: {response}")
        return response
