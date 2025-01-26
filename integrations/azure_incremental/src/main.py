import asyncio
from typing import Any, Coroutine, Generator

import httpx
from src.utils import turn_sequence_to_chunks
from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.services.resources import sync_resources
from src.services.resource_containers import sync_resource_containers
from src.queries import RESOURCE_CHANGES_QUERY
from loguru import logger
from src.settings import app_settings

from azure.mgmt.subscription.models._models_py3 import Subscription


async def upsert_subscriptions(
    subscriptions: list[Subscription], port_client: PortClient
) -> None:
    """
    Constructs the subscription entities and upserts them in Port
    """
    logger.info(f"Upserting {len(subscriptions)} subscriptions")
    tasks: list[Coroutine[Any, Any, None]] = []
    tasks.extend(
        port_client.send_webhook_data(
            subscription.as_dict(),
            id=subscription.id,
            operation="upsert",
            type="subscription",
        )
        for subscription in subscriptions
    )

    await asyncio.gather(*tasks)


async def process_change_items(
    items: list[dict[str, Any]], port_client: PortClient
) -> tuple[
    list[Coroutine[Any, Any, None]],
    list[Coroutine[Any, Any, None]],
]:
    """
    Processes the changes retrieved from Azure and decides
    whether to upsert or delete them.
    The upserts and deletions are returned as tasks to be run concurrently.
    """
    delete_tasks = []
    upsert_tasks = []

    for item in items:
        if item["changeType"] == "Delete":
            delete_tasks.append(
                port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="delete",
                    type="resource",
                )
            )
        else:
            upsert_tasks.append(
                port_client.send_webhook_data(
                    data=item,
                    id=item["resourceId"],
                    operation="upsert",
                    type="resource",
                )
            )

    return delete_tasks, upsert_tasks


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

        for subscriptions in subscriptions_batches:
            await sync_resources(
                [s.subscription_id for s in subscriptions],
                azure_client,
                port_client,
            )

            await sync_resource_containers(
                [s.subscription_id for s in subscriptions],
                azure_client,
                port_client,
            )

    logger.success("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
