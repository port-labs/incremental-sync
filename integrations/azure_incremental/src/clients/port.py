import asyncio
from typing import Any

import httpx
from loguru import logger
from src.settings import app_settings

class PortClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.http_client = http_client
        self.webhook_ingest_url = app_settings.PORT_WEBHOOK_INGEST_URL
        self.webhook_secret = app_settings.PORT_WEBHOOK_SECRET
        self.semaphore = asyncio.Semaphore(100)

    @classmethod
    def _handle_error(cls, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send data to webhook: {e}")
            logger.error(f"Response: {response.json()}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Failed to send data to webhook: {e}")
            raise

    async def send_webhook_data(self, data: dict[str, Any], id: str, operation: str, type: str) -> None:
        async with self.semaphore:
            body_json = {
                "data": data,
                "operation": operation,
                "type": type,
            }

            logger.info(f"Sending {operation} request to webhook for type: {type}, id: {id}")
            await self.http_client.post(
                self.webhook_ingest_url,
                json=body_json,
            )
            logger.info(f"Sent {operation} request to webhook for type: {type}, id: {id}")

    @classmethod
    def construct_resource_group_entity(
        cls, name: str, subscription_id: str
    ) -> dict[str, Any]:
        return {
            "name": name,
            "subscriptionId": subscription_id,
            "__typename": "ResourceGroup",
        }
