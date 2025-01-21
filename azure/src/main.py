import asyncio
from typing import Any, Generator

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


async def main() -> None:
    logger.info("Starting Azure to Port sync")
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(20)) as client,
        AzureClient() as azure_client,
    ):
        port_client = initialize_port_client(client)
        token = await port_client.get_port_token()
        client.headers.update({"Authorization": f"Bearer {token}"})

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
        logger.info(f"Sync is starting with state: {state}")

        subs = []
        async for sub in azure_client.get_all_subscriptions():
            subs.append(sub)

        logger.info(f"Found {len(subs)} subscriptions in Azure")
        logger.debug(f"Subscriptions: {subs}")

        subscriptions_batches: Generator[list[Subscription], None, None] = (
            utils.turn_sequence_to_chunks(
                subs,
                1000,
            )
        )

        query = (
            INITIAL_QUERY
            if state["properties"]["value"] == "INITIAL"
            else SUBSEQUENT_QUERY
        )

        for subscriptions in subscriptions_batches:
            logger.info(
                "Running query for subscription batch with "
                f"{len(subscriptions)} subscriptions"
            )

            data = await azure_client.run_query(
                query,
                [s.subscription_id for s in subscriptions],  # type: ignore
            )
            logger.info(f"Received data: {data}")
            delete_tasks = []
            upsert_tasks = []

            for item in data:
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

            logger.info(
                f"Running {len(delete_tasks)} delete tasks "
                f"and {len(upsert_tasks)} upsert tasks"
            )
            await asyncio.gather(*delete_tasks)
            await asyncio.gather(*upsert_tasks)

        await port_client.upsert_data(
            STATE_BLUEPRINT["identifier"],
            {**state, "properties": {"value": "SUBSEQUENT"}},
        )

    logger.info("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
