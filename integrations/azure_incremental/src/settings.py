import json
from enum import StrEnum
from typing import Dict

from pydantic_settings import BaseSettings


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
    # Resource Group tag filtering settings
    RESOURCE_GROUP_TAG_FILTERS: str | None = None  # JSON string of key-value pairs
    EXCLUDE_RESOURCES_BY_RG_TAGS: bool = (
        False  # Whether to exclude (True) or include (False) based on tags
    )

    def get_resource_group_tag_filters(self) -> Dict[str, str] | None:
        """Parse the RESOURCE_GROUP_TAG_FILTERS JSON string into a dictionary."""
        if not self.RESOURCE_GROUP_TAG_FILTERS:
            return None
        try:
            result = json.loads(self.RESOURCE_GROUP_TAG_FILTERS)
            if isinstance(result, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in result.items()
            ):
                return result
            return None
        except json.JSONDecodeError:
            return None


app_settings = _AppSettings()


__all__ = ["app_settings"]
