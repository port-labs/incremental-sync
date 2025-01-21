import asyncio
from typing import Any, Coroutine, Generator

import httpx
import utils
from clients.azure_client import AzureClient
from clients.port import PortClient
from constants import (
    CLOUD_RESOURCES_BLUEPRINT,
    INITIAL_QUERY,
    RESOURCES_GROUP_BLUEPRINT,
    STATE_BLUEPRINT,
    STATE_DATA,
    SUBSCRIPTION_BLUEPRINT,
    SUBSEQUENT_QUERY,
)
from loguru import logger
from settings import app_settings

from azure.mgmt.subscription.models._models_py3 import Subscription


def initialize_port_client(client: httpx.AsyncClient) -> PortClient:
    return PortClient(
        client,
        app_settings.PORT_CLIENT_ID,
        app_settings.PORT_CLIENT_SECRET,
        app_settings.PORT_API_URL,
    )


async def initialize_blueprints(port_client: PortClient) -> None:
    """
    Create the blueprints in Port if they don't exist
    """

    tasks = [
        port_client.upsert_blueprint(STATE_BLUEPRINT),
        port_client.upsert_blueprint(CLOUD_RESOURCES_BLUEPRINT),
        port_client.upsert_blueprint(RESOURCES_GROUP_BLUEPRINT),
        port_client.upsert_blueprint(SUBSCRIPTION_BLUEPRINT),
    ]
    await asyncio.gather(*tasks)

    logger.info(
        "The following blueprints were initialized in Port:"
        f" {STATE_BLUEPRINT['identifier']},"
        f" {CLOUD_RESOURCES_BLUEPRINT['identifier']},"
        f" {RESOURCES_GROUP_BLUEPRINT['identifier']},"
        f" {SUBSCRIPTION_BLUEPRINT['identifier']}"
    )


async def initialize_state(port_client: PortClient) -> dict[str, Any]:
    """
    Retrieve the state from Port or create it if it doesn't exist
    """

    logger.info("Retrieving state from Port to determine the sync stage")
    state_response = await port_client.retrieve_data(
        STATE_BLUEPRINT["identifier"], STATE_DATA["identifier"]
    )
    if not state_response:
        logger.info("State not found, creating initial state")
        state_response = await port_client.upsert_data(
            STATE_BLUEPRINT["identifier"], STATE_DATA
        )
    state: dict[str, Any] = state_response["entity"]
    return state


async def upsert_subscriptions(
    subscriptions: list[Subscription], port_client: PortClient
) -> None:
    """
    Constructs the subscription entities and upserts them in Port
    """
    logger.info(f"Upserting {len(subscriptions)} subscriptions")
    tasks = []
    for subscription in subscriptions:
        entity = port_client.construct_subscription_entity(subscription)
        tasks.append(
            port_client.upsert_data(
                SUBSCRIPTION_BLUEPRINT["identifier"], entity
            )
        )

    await asyncio.gather(*tasks)


async def upsert_resources_groups(
    r_groups: list[tuple[str, str]], port_client: PortClient
) -> None:
    """
    Constructs the resource group entities and upserts them in Port
    """
    tasks = []
    for r_group in r_groups:
        entity = port_client.construct_resource_group_entity(*r_group)
        tasks.append(
            port_client.upsert_data(
                RESOURCES_GROUP_BLUEPRINT["identifier"], entity
            )
        )

    await asyncio.gather(*tasks)


async def process_change_items(
    items: list[dict[str, Any]], port_client: PortClient
) -> tuple[
    list[Coroutine[Any, Any, dict[str, Any]]],
    list[Coroutine[Any, Any, dict[str, Any]]],
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
            delete_tasks.append(
                port_client.delete_data(
                    CLOUD_RESOURCES_BLUEPRINT["identifier"], entity
                )
            )
        else:
            upsert_tasks.append(
                port_client.upsert_data(
                    CLOUD_RESOURCES_BLUEPRINT["identifier"], entity
                )
            )

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
        await asyncio.gather(*delete_tasks)
        await asyncio.gather(*upsert_tasks)


async def main() -> None:
    logger.info("Starting Azure to Port sync")
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(20)) as client,
        AzureClient() as azure_client,
    ):
        port_client = initialize_port_client(client)
        token = await port_client.get_port_token()
        client.headers.update({"Authorization": f"Bearer {token}"})

        await initialize_blueprints(port_client)

        state = await initialize_state(port_client)
        logger.info(f"Sync is starting with state: {state}")

        subs = await azure_client.get_all_subscriptions()
        logger.debug(f"Subscriptions: {subs}")

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            utils.turn_sequence_to_chunks(
                subs,
                app_settings.SUBSCRIPTION_BATCH_SIZE,
            )
        )

        query = (
            INITIAL_QUERY
            if state["properties"]["value"] == "INITIAL"
            else SUBSEQUENT_QUERY
        )
        logger.info(query)

        for subscriptions in subscriptions_batches:
            await upsert_subscriptions(subscriptions, port_client)
            await process_subscriptions_into_change_tasks(
                [s.subscription_id for s in subscriptions],
                query,
                azure_client,
                port_client,
            )

        await port_client.upsert_data(
            STATE_BLUEPRINT["identifier"],
            {**state, "properties": {"value": "SUBSEQUENT"}},
        )

    logger.info("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
