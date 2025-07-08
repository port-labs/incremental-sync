import json
from enum import StrEnum
from typing import Dict, Optional

from loguru import logger
from pydantic_settings import BaseSettings


class SyncMode(StrEnum):
    incremental = "incremental"
    full = "full"


class ResourceGroupTagFilters:
    """Class to represent resource group tag filters with include/exclude logic."""

    def __init__(
        self,
        include: Optional[Dict[str, str]] = None,
        exclude: Optional[Dict[str, str]] = None,
    ):
        self.include = include or {}
        self.exclude = exclude or {}

    def has_filters(self) -> bool:
        """Check if any filters are configured."""
        return bool(self.include) or bool(self.exclude)

    def __repr__(self) -> str:
        return (
            f"ResourceGroupTagFilters(include={self.include}, exclude={self.exclude})"
        )


class _AppSettings(BaseSettings):
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    PORT_WEBHOOK_INGEST_URL: str
    PORT_WEBHOOK_SECRET: str = "azure-incremental"
    SUBSCRIPTION_BATCH_SIZE: int = 1000
    CHANGE_WINDOW_MINUTES: int = 15
    SYNC_MODE: SyncMode = SyncMode.full
    RESOURCE_TYPES: list[str] | None = None
    RESOURCE_GROUP_TAG_FILTERS: str | None = (
        None  # JSON string e.g '{"include": {"environment": "prod"}, "exclude": {"environment": "dev"}}'
    )

    def get_resource_group_tag_filters(self) -> ResourceGroupTagFilters:
        """Parse the RESOURCE_GROUP_TAG_FILTERS JSON string into ResourceGroupTagFilters object."""
        if not self.RESOURCE_GROUP_TAG_FILTERS:
            return ResourceGroupTagFilters()

        try:
            parsed = json.loads(self.RESOURCE_GROUP_TAG_FILTERS)

            if isinstance(parsed, dict) and (
                "include" in parsed or "exclude" in parsed
            ):
                include_filters = parsed.get("include", {})
                exclude_filters = parsed.get("exclude", {})

                # Validate that include/exclude are dictionaries with string key-value pairs
                if (
                    isinstance(include_filters, dict)
                    and isinstance(exclude_filters, dict)
                    and all(
                        isinstance(k, str) and isinstance(v, str)
                        for k, v in include_filters.items()
                    )
                    and all(
                        isinstance(k, str) and isinstance(v, str)
                        for k, v in exclude_filters.items()
                    )
                ):
                    return ResourceGroupTagFilters(
                        include=include_filters, exclude=exclude_filters
                    )

            return ResourceGroupTagFilters()

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse RESOURCE_GROUP_TAG_FILTERS: {self.RESOURCE_GROUP_TAG_FILTERS}. "
                f"Error: {e}"
            )
            return ResourceGroupTagFilters()


app_settings = _AppSettings()


__all__ = ["app_settings"]
