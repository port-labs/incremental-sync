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


def initialize_azure_client() -> AzureClient:
    return AzureClient()


async def main() -> None:
    logger.info("Starting Azure to Port sync")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20)) as client:
        port_client = initialize_port_client(client)
        azure_client = initialize_azure_client()
        token = await port_client.get_port_token()
        client.headers.update({"Authorization": f"Bearer {token}"})

        tasks = [
            port_client.upsert_blueprint(STATE_BLUEPRINT),
            port_client.upsert_blueprint(CLOUD_RESOURCES_BLUEPRINT),
            port_client.upsert_blueprint(RESOURCES_GROUP_BLUEPRINT),
            port_client.upsert_blueprint(SUBSCRIPTION_BLUEPRINT),
        ]
        await asyncio.gather(*tasks)

        state_response = await port_client.retrieve_data(
            STATE_BLUEPRINT["identifier"], STATE_DATA["identifier"]
        )
        if not state_response:
            state_response = await port_client.upsert_data(
                STATE_BLUEPRINT["identifier"], STATE_DATA
            )

        state: dict[str, Any] = state_response["entity"]
        subs = []
        async for sub in azure_client.get_all_subscriptions():
            subs.append(sub)

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
            data = await azure_client.run_query(
                query,
                [s.subscription_id for s in subscriptions],  # type: ignore
            )
            logger.info(f"Received data: {data}")
            delete_tasks = []
            upsert_tasks = []
            for item in data:
                entity = port_client.construct_resources_entity(item)
                if item["action"] == "delete":
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

            await asyncio.gather(*delete_tasks)
            await asyncio.gather(*upsert_tasks)

        await port_client.upsert_data(
            STATE_BLUEPRINT["identifier"],
            {**state, "properties": {"value": "SUBSEQUENT"}},
        )

    logger.info("Azure to Port sync completed")


if __name__ == "__main__":
    asyncio.run(main())
