from typing import Any

import httpx
from loguru import logger
from settings import app_settings
from utils import AzureResourceQueryData

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

    async def _send_request(
        self, method: str, url: str, handle_error: bool = True, **kwargs: Any
    ) -> httpx.Response:
        response = await self.http_client.request(method, url, **kwargs)
        if handle_error:
            self._handle_error(response)
        return response

    async def upsert_data(self, data: dict[str, Any]) -> None:
        logger.info("Sending upsert request to webhook")
        await self._send_request(
            "post",
            app_settings.PORT_WEBHOOK_INGEST_URL,
            json=data,
        )
        logger.info("Sent data to webhook successfully")

    async def delete_data(self, data: dict[str, Any]) -> None:
        logger.info("Sending delete request to webhook")
        await self._send_request(
            "delete",
            app_settings.PORT_WEBHOOK_INGEST_URL,
            json=data,
        )
        logger.info("Sent delete request to webhook successfully")

    async def retrieve_data(
        self, blueprint: str, id: str
    ) -> dict[str, Any] | None:
        logger.info(f"Retrieving data for blueprint {blueprint} with id {id}")
        response = await self._send_request(
            "get",
            f"{self.api_url}/blueprints/{blueprint}/entities/{id}",
            handle_error=False,
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

    @classmethod
    def construct_resources_entity(
        cls, data: AzureResourceQueryData
    ) -> dict[str, Any]:
        return {
            **data,
            "__typename": "Resource",
        }

    @classmethod
    def construct_subscription_entity(
        cls, data: Subscription
    ) -> dict[str, Any]:
        return {
            "id": data.id,
            "subscriptionId": data.subscription_id,
            "displayName": data.display_name,
            "additionalProperties": data.additional_properties,
            "authorizationSource": data.authorization_source,
            "state": data.state,
            "subscriptionPolicies": data.subscription_policies
            and {
                "locationPlacementId": (
                    data.subscription_policies.location_placement_id
                ),
                "quotaId": data.subscription_policies.quota_id,
                "spendingLimit": data.subscription_policies.spending_limit,
            },
            "__typename": "Subscription",
        }

    @classmethod
    def construct_resource_group_entity(
        cls, name: str, subscription_id: str
    ) -> dict[str, Any]:
        return {
            "name": name,
            "subscriptionId": subscription_id,
            "__typename": "ResourceGroup",
        }
