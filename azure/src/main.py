import asyncio
from typing import Any, Coroutine, Generator

import httpx
import utils
from clients.azure_client import AzureClient
from clients.port import PortClient
from constants import QUERY
from loguru import logger
from settings import app_settings
from utils import AzureResourceQueryData

from azure.mgmt.subscription.models._models_py3 import Subscription


def initialize_port_client(client: httpx.AsyncClient) -> PortClient:
    return PortClient(
        client,
        app_settings.PORT_CLIENT_ID,
        app_settings.PORT_CLIENT_SECRET,
        app_settings.PORT_API_URL,
    )


async def upsert_subscriptions(
    subscriptions: list[Subscription], port_client: PortClient
) -> None:
    """
    Constructs the subscription entities and upserts them in Port
    """
    logger.info(f"Upserting {len(subscriptions)} subscriptions")
    tasks: list[Coroutine[Any, Any, None]] = []
    tasks.extend(
        port_client.upsert_data(
            port_client.construct_subscription_entity(subscription),
        )
        for subscription in subscriptions
    )

    await asyncio.gather(*tasks)


async def upsert_resources_groups(
    r_groups: list[tuple[str, str]], port_client: PortClient
) -> None:
    """
    Constructs the resource group entities and upserts them in Port
    """
    tasks: list[Coroutine[Any, Any, None]] = []
    tasks.extend(
        port_client.upsert_data(
            port_client.construct_resource_group_entity(*r_group)
        )
        for r_group in r_groups
    )

    await asyncio.gather(*tasks)


async def process_change_items(
    items: list[AzureResourceQueryData], port_client: PortClient
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
    resource_groups: list[tuple[str, str]] = []

    for item in items:
        resource_groups.append((item["resourceGroup"], item["subscriptionId"]))
        entity = port_client.construct_resources_entity(item)
        if item["changeType"] == "Delete":
            delete_tasks.append(port_client.delete_data(entity))
        else:
            upsert_tasks.append(port_client.upsert_data(entity))

    await upsert_resources_groups(resource_groups, port_client)

    return delete_tasks, upsert_tasks


async def process_subscriptions_into_change_tasks(
    subscriptions: list[str | None],
    query: str,
    azure_client: AzureClient,
    port_client: PortClient,
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

    async for items in azure_client.run_query(
        query,
        subscriptions,  # type: ignore
    ):
        logger.info(f"Received batch of {len(items)} resource operations")
        delete_tasks, upsert_tasks = await process_change_items(
            items, port_client
        )

        logger.info(
            f"Running {len(delete_tasks)} delete tasks "
            f"and {len(upsert_tasks)} upsert tasks"
        )
        await asyncio.gather(*upsert_tasks)
        await asyncio.gather(*delete_tasks)


async def main() -> None:
    logger.info("Starting Azure to Port sync")
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(20)) as client,
        AzureClient() as azure_client,
    ):
        port_client = initialize_port_client(client)

        subscriptions = await azure_client.get_all_subscriptions()
        logger.info(f"Discovered {len(subscriptions)} subscriptions")
        logger.debug(f"Subscriptions: {subscriptions}")

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            utils.turn_sequence_to_chunks(
                subscriptions,
                app_settings.SUBSCRIPTION_BATCH_SIZE,
            )
        )

        query = QUERY

        for subscriptions in subscriptions_batches:
            await upsert_subscriptions(subscriptions, port_client)
            await process_subscriptions_into_change_tasks(
                [s.subscription_id for s in subscriptions],
                query,
                azure_client,
                port_client,
            )

        logger.success("Azure to Port sync completed")

    logger.info("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
