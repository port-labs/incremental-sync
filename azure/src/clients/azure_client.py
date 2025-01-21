from typing import Any, AsyncIterable, Self

from loguru import logger

from azure.identity.aio import DefaultAzureCredential
from azure.mgmt.resourcegraph.aio import ResourceGraphClient  # type: ignore
from azure.mgmt.resourcegraph.models import (  # type: ignore
    QueryRequest,
    QueryRequestOptions,
    ResultFormat,
)
from azure.mgmt.subscription.aio import SubscriptionClient
from azure.mgmt.subscription.models._models_py3 import Subscription


class AzureClient:
    def __init__(self) -> None:
        self._credentials: DefaultAzureCredential | None = None
        self.subs_client: SubscriptionClient | None = None
        self.resource_g_client: ResourceGraphClient | None = None

    async def get_all_subscriptions(self) -> AsyncIterable[Subscription]:
        logger.info("Getting all Azure subscriptions")
        if not self.subs_client:
            raise ValueError("Azure client not initialized")
        async for sub in self.subs_client.subscriptions.list():
            yield sub

    async def run_query(
        self, query: str, subscriptions: list[str]
    ) -> list[dict[str, Any]]:
        logger.info("Running query")
        if not self.resource_g_client:
            raise ValueError("Azure client not initialized")

        query = QueryRequest(
            subscriptions=subscriptions,
            query=query,
            options=QueryRequestOptions(
                result_format=ResultFormat.OBJECT_ARRAY
            ),
        )
        response: list[dict[str, Any]] = (
            await self.resource_g_client.resources(query)
        ).data
        logger.info(f"Query ran successfully with response: {response}")
        return response

    async def __aenter__(self) -> Self:
        logger.info("Initializing Azure connection resources")
        self._credentials = DefaultAzureCredential()
        self.subs_client = SubscriptionClient(self._credentials)
        self.resource_g_client = ResourceGraphClient(self._credentials)
        return self

    async def __aexit__(
        self, exc_type: Exception, exc_value: Exception, traceback: Any
    ) -> None:
        logger.info("Cleaning up Azure connection resources")
        if self.subs_client is not None:
            await self.subs_client.close()
        if self.resource_g_client is not None:
            await self.resource_g_client.close()
        if self._credentials is not None:
            await self._credentials.close()
