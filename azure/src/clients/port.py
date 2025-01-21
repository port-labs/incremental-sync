from typing import Any

import httpx
from loguru import logger

from azure.mgmt.subscription.models._models_py3 import Subscription


class PortClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        api_url: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_url = api_url
        self.http_client = http_client

    @classmethod
    def _handle_error(cls, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to upsert data: {e}")
            logger.error(f"Response: {response.json()}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Failed to upsert data: {e}")
            raise

    async def get_port_token(self) -> str:
        logger.info("Getting Port token")
        response = await self.http_client.post(
            f"{self.api_url}/auth/access_token",
            data={
                "clientId": self.client_id,
                "clientSecret": self.client_secret,
            },
        )
        self._handle_error(response)
        logger.info("Retrieved Port token successfully")
        result: dict[str, str] = response.json()
        return result["accessToken"]

    async def upsert_blueprint(self, data: dict[str, Any]) -> dict[str, Any]:
        logger.info(f"Upserting blueprint {data['identifier']}")

        if blueprint := await self.get_blueprint(data["identifier"]):
            logger.info(
                f"Blueprint {data['identifier']}"
                "already exists, skipping creation"
            )

            return blueprint

        response = await self.http_client.post(
            f"{self.api_url}/blueprints", json=data
        )
        self._handle_error(response)
        logger.info(f"Upserted blueprint {data['identifier']} successfully")
        result: dict[str, Any] = response.json()
        return result

    async def get_blueprint(self, blueprint: str) -> dict[str, Any]:
        logger.info(f"Getting blueprint {blueprint}")
        response = await self.http_client.get(
            f"{self.api_url}/blueprints/{blueprint}"
        )
        if response.status_code == 404:
            logger.info(f"No blueprint found for {blueprint}")
            return {}

        self._handle_error(response)
        logger.info(f"Retrieved blueprint {blueprint} successfully")
        result: dict[str, Any] = response.json()
        return result

    async def upsert_data(
        self, blueprint: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        logger.info(f"Upserting blueprint {blueprint} with data {data}")
        response = await self.http_client.post(
            (
                f"{self.api_url}/blueprints/{blueprint}/entities"
                "?upsert=true&merge=true&create_missing_related_entities=true"
            ),
            json=data,
        )
        self._handle_error(response)
        logger.info(f"Upserted blueprint {blueprint} successfully")
        result: dict[str, Any] = response.json()
        return result

    async def retrieve_data(
        self, blueprint: str, id: str
    ) -> dict[str, Any] | None:
        logger.info(f"Retrieving data for blueprint {blueprint} with id {id}")
        response = await self.http_client.get(
            f"{self.api_url}/blueprints/{blueprint}/entities/{id}"
        )
        if response.status_code == 404:
            logger.info(
                f"No data found for blueprint {blueprint} with id {id}"
            )
            return None
        self._handle_error(response)
        logger.info(f"Retrieved data for blueprint {blueprint} with id {id}")
        result: dict[str, Any] = response.json()
        return result

    async def delete_data(
        self, blueprint: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        logger.info(f"Deleting blueprint {blueprint} with data {data}")
        response = await self.http_client.post(
            (
                f"{self.api_url}/blueprints/{blueprint}/entities?delete_dependents=false"
            ),
            json=data,
        )
        self._handle_error(response)
        logger.info(f"Deleted blueprint {blueprint} successfully")
        result: dict[str, Any] = response.json()
        return result

    @classmethod
    def construct_resources_entity(
        cls, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "identifier": data["resourceId"],
            "title": data["name"],
            "properties": {
                "tags": data["tags"],
                "type": data["type"],
                "location": data["location"],
                "changeType": data["changeType"],
                "changeTime": data["changeTime"],
            },
            "relations": {
                "subscription": data["subscriptionId"],
                "resourceGroup": data["resourceGroup"],
            },
        }

    @classmethod
    def construct_subscription_entity(
        cls, data: Subscription
    ) -> dict[str, Any]:
        return {
            "identifier": data.subscription_id,
            "title": data.display_name,
            "properties": {"tags": data.additional_properties},
        }

    @classmethod
    def construct_resource_group_entity(
        cls, name: str, subscription_id: str
    ) -> dict[str, Any]:
        return {
            "identifier": name,
            "title": name,
            "relations": {"subscription": subscription_id},
        }
