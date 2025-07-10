import json
from enum import StrEnum
from typing import Dict, Optional

from loguru import logger
from pydantic_settings import BaseSettings


class SyncMode(StrEnum):
    incremental = "incremental"
    full = "full"


TagFilter = Dict[str, str]
FilterJSON = Dict[str, TagFilter]


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
    SYNC_MODE: SyncMode = SyncMode.incremental
    RESOURCE_TYPES: Optional[list[str]] = None
    RESOURCE_GROUP_TAG_FILTERS: Optional[str] = None  # JSON string

    def get_resource_group_tag_filters(self) -> ResourceGroupTagFilters:
        """
        Converts RESOURCE_GROUP_TAG_FILTERS JSON string into a ResourceGroupTagFilters object.
        Returns an empty object if parsing or validation fails.
        """
        if not self.RESOURCE_GROUP_TAG_FILTERS:
            return ResourceGroupTagFilters()

        parsed = self._parse_json(self.RESOURCE_GROUP_TAG_FILTERS)
        if parsed is None:
            return ResourceGroupTagFilters()

        if not self._is_valid_filter_structure(parsed):
            logger.warning(
                f"Invalid structure in RESOURCE_GROUP_TAG_FILTERS: {self.RESOURCE_GROUP_TAG_FILTERS}. "
                "Expected JSON object with string key-value pairs in 'include' and/or 'exclude'."
            )
            return ResourceGroupTagFilters()

        return ResourceGroupTagFilters(
            include=parsed.get("include", {}),
            exclude=parsed.get("exclude", {}),
        )

    def _parse_json(self, raw_json: str) -> Optional[FilterJSON]:
        """Parses a JSON string and returns a dict if valid."""
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict):
                return data
            logger.warning(
                f"Expected a JSON object in RESOURCE_GROUP_TAG_FILTERS but got: {type(data).__name__}"
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse RESOURCE_GROUP_TAG_FILTERS: {raw_json}. Error: {e}"
            )
        return None

    def _is_valid_filter_structure(self, data: FilterJSON) -> bool:
        """
        Validates that 'include' and 'exclude' are optional keys with string-to-string mappings.
        """
        for key in ("include", "exclude"):
            filters = data.get(key)
            if filters is not None:
                if not isinstance(filters, dict):
                    return False
                if not all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in filters.items()
                ):
                    return False
        return True


app_settings = _AppSettings()


__all__ = ["app_settings"]
