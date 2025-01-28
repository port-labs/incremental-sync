import asyncio
from typing import Generator

import httpx
from src.utils import turn_sequence_to_chunks
from src.clients.azure_client import AzureClient
from src.clients.port import PortClient

from loguru import logger
from src.settings import app_settings, SyncMode

from azure.mgmt.subscription.models._models_py3 import Subscription

from src.services.resource_containers import ResourceContainers
from src.services.resources import Resources


async def main() -> None:
    logger.info("Starting Azure to Port sync")
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(20)) as client,
        AzureClient() as azure_client,
    ):
        port_client = PortClient(client)

        all_subscriptions = await azure_client.get_all_subscriptions()
        logger.info(f"Discovered {len(all_subscriptions)} subscriptions")

        if not all_subscriptions:
            logger.error("No subscriptions found in Azure, exiting")
            return

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            turn_sequence_to_chunks(
                all_subscriptions,
                app_settings.SUBSCRIPTION_BATCH_SIZE,
            )
        )

        resource_containers = ResourceContainers(azure_client, port_client)
        resources = Resources(azure_client, port_client)

        for subscriptions in subscriptions_batches:
            if app_settings.SYNC_MODE == SyncMode.incremental:
                await resource_containers.sync_incremental(
                    [s.subscription_id for s in subscriptions],
                )
                await resources.sync_incremental(
                    [s.subscription_id for s in subscriptions],
                )
            else:
                await resource_containers.sync_full(
                    [s.subscription_id for s in subscriptions],
                )
                await resources.sync_full(
                    [s.subscription_id for s in subscriptions],
                )

    logger.success("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
