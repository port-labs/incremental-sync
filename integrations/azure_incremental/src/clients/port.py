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
        self.semaphore = asyncio.Semaphore(25)

    async def send_webhook_data(
        self, data: dict[str, Any], id: str, operation: str, type: str
    ) -> None:
        async with self.semaphore:
            body_json = {
                "data": data,
                "operation": operation,
                "type": type,
            }

            logger.info(
                f"Sending {operation} request to webhook for type: {type}, id: {id}"
            )
            retries = 3
            while retries > 0:
                try:
                    response = await self.http_client.post(
                        self.webhook_ingest_url,
                        json=body_json,
                    )
                    response.raise_for_status()
                    logger.info(
                        f"Successfully sent {operation} request to webhook for type: {type}, id: {id}"
                    )
                    break
                except Exception as e:
                    logger.error(
                        f"Failed to send data to webhook: {e}, operation: {operation}, type: {type}, id: {id}"
                    )
                    logger.info("Retrying to send data to webhook")
                    await asyncio.sleep(1)
                    retries -= 1
