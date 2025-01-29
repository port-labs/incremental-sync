from pydantic_settings import BaseSettings
from enum import StrEnum


class SyncMode(StrEnum):
    incremental = "incremental"
    full = "full"

class _AppSettings(BaseSettings):
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    PORT_WEBHOOK_INGEST_URL: str
    PORT_WEBHOOK_SECRET: str = "azure-incremental"
    SUBSCRIPTION_BATCH_SIZE: int = 1000
    CHANGE_WINDOW_MINUTES: int = 15
    SYNC_MODE: SyncMode = SyncMode.incremental
    RESOURCE_TYPES: list[str] | None = None


app_settings = _AppSettings()


__all__ = ["app_settings"]
