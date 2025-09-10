from typing import Any, Dict
from unittest.mock import patch

from src.settings import ResourceGroupTagFilters, app_settings


class TestResourceGroupTagFilters:
    """Test the ResourceGroupTagFilters class."""

    def test_empty_filters(self) -> None:
        """Test creating empty filters."""
        filters = ResourceGroupTagFilters()
        assert filters.include == {}
        assert filters.exclude == {}
        assert not filters.has_filters()

    def test_include_only_filters(self) -> None:
        """Test creating filters with include only."""
        include_filters: Dict[str, str] = {
            "Environment": "Production",
            "Team": "Platform",
        }
        filters = ResourceGroupTagFilters(include=include_filters)
        assert filters.include == include_filters
        assert filters.exclude == {}
        assert filters.has_filters()

    def test_exclude_only_filters(self) -> None:
        """Test creating filters with exclude only."""
        exclude_filters: Dict[str, str] = {"Temporary": "true", "Stage": "deprecated"}
        filters = ResourceGroupTagFilters(exclude=exclude_filters)
        assert filters.include == {}
        assert filters.exclude == exclude_filters
        assert filters.has_filters()

    def test_both_include_and_exclude_filters(self) -> None:
        """Test creating filters with both include and exclude."""
        include_filters: Dict[str, str] = {"Environment": "Production"}
        exclude_filters: Dict[str, str] = {"Temporary": "true"}
        filters = ResourceGroupTagFilters(
            include=include_filters, exclude=exclude_filters
        )
        assert filters.include == include_filters
        assert filters.exclude == exclude_filters
        assert filters.has_filters()

    def test_repr(self) -> None:
        """Test the string representation."""
        filters = ResourceGroupTagFilters(
            include={"Environment": "Production"},
            exclude={"Temporary": "true"},
        )
        repr_str = repr(filters)
        assert "ResourceGroupTagFilters" in repr_str
        assert "include=" in repr_str
        assert "exclude=" in repr_str


class TestAppSettings:
    """Test the app settings functionality."""

    @patch.dict(
        "os.environ",
        {
            "AZURE_CLIENT_ID": "test-client-id",
            "AZURE_CLIENT_SECRET": "test-client-secret",
            "AZURE_TENANT_ID": "test-tenant-id",
            "PORT_WEBHOOK_INGEST_URL": "https://test-port.com/webhook",
            "PORT_WEBHOOK_SECRET": "test-secret",
            "CHANGE_WINDOW_MINUTES": "15",
            "SUBSCRIPTION_BATCH_SIZE": "1000",
            "SYNC_MODE": "incremental",
        },
    )
    def test_default_settings(self) -> None:
        """Test default settings values."""
        # The settings should be loaded automatically by pydantic
        from src.settings import app_settings

        assert app_settings.AZURE_CLIENT_ID == "test-client-id"
        assert app_settings.AZURE_CLIENT_SECRET == "test-client-secret"
        assert app_settings.PORT_WEBHOOK_INGEST_URL == "https://test-port.com/webhook"
        assert app_settings.PORT_WEBHOOK_SECRET == "test-secret"
        assert app_settings.CHANGE_WINDOW_MINUTES == 15
        assert app_settings.SUBSCRIPTION_BATCH_SIZE == 1000
        assert app_settings.SYNC_MODE == "incremental"

    def test_get_resource_group_tag_filters_empty(self) -> None:
        """Test getting empty tag filters."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = None
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_get_resource_group_tag_filters_valid_include(self) -> None:
        """Test getting valid include-only filters."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = (
            '{"include": {"Environment": "Production"}}'
        )
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert filters.include == {"Environment": "Production"}
        assert filters.exclude == {}
        assert filters.has_filters()

    def test_get_resource_group_tag_filters_valid_exclude(self) -> None:
        """Test getting valid exclude-only filters."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"exclude": {"Temporary": "true"}}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert filters.include == {}
        assert filters.exclude == {"Temporary": "true"}
        assert filters.has_filters()

    def test_get_resource_group_tag_filters_valid_both(self) -> None:
        """Test getting valid include and exclude filters."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"include": {"Environment": "Production"}, "exclude": {"Temporary": "true"}}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert filters.include == {"Environment": "Production"}
        assert filters.exclude == {"Temporary": "true"}
        assert filters.has_filters()

    def test_get_resource_group_tag_filters_invalid_json(self) -> None:
        """Test handling invalid JSON."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = "invalid json"
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_get_resource_group_tag_filters_invalid_structure(self) -> None:
        """Test handling invalid filter structure."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"invalid": "structure"}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_get_resource_group_tag_filters_invalid_include_type(self) -> None:
        """Test handling invalid include filter type."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"include": "not a dict"}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_get_resource_group_tag_filters_invalid_exclude_type(self) -> None:
        """Test handling invalid exclude filter type."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"exclude": "not a dict"}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_get_resource_group_tag_filters_non_string_values(self) -> None:
        """Test handling non-string values in filters."""
        app_settings.RESOURCE_GROUP_TAG_FILTERS = '{"include": {"Environment": 123}}'
        filters = app_settings.get_resource_group_tag_filters()
        assert isinstance(filters, ResourceGroupTagFilters)
        assert not filters.has_filters()

    def test_parse_json_valid(self) -> None:
        """Test parsing valid JSON."""
        result = app_settings._parse_json('{"include": {"Environment": "Production"}}')
        assert result == {"include": {"Environment": "Production"}}

    def test_parse_json_invalid(self) -> None:
        """Test parsing invalid JSON."""
        result = app_settings._parse_json("invalid json")
        assert result is None

    def test_parse_json_not_dict(self) -> None:
        """Test parsing JSON that's not a dict."""
        result = app_settings._parse_json('["not", "a", "dict"]')
        assert result is None

    def test_is_valid_filter_structure_valid(self) -> None:
        """Test validating valid filter structure."""
        data: Dict[str, Any] = {
            "include": {"Environment": "Production"},
            "exclude": {"Temporary": "true"},
        }
        assert app_settings._is_valid_filter_structure(data) is True

    def test_is_valid_filter_structure_invalid_include_type(self) -> None:
        """Test validating invalid include filter type."""
        data: Dict[str, Any] = {"include": "not a dict"}
        assert app_settings._is_valid_filter_structure(data) is False

    def test_is_valid_filter_structure_invalid_exclude_type(self) -> None:
        """Test validating invalid exclude filter type."""
        data: Dict[str, Any] = {"exclude": "not a dict"}
        assert app_settings._is_valid_filter_structure(data) is False

    def test_is_valid_filter_structure_non_string_values(self) -> None:
        """Test validating filters with non-string values."""
        data: Dict[str, Any] = {"include": {"Environment": 123}}
        assert app_settings._is_valid_filter_structure(data) is False

    def test_is_valid_filter_structure_empty(self) -> None:
        """Test validating empty filter structure."""
        data: Dict[str, Any] = {}
        assert app_settings._is_valid_filter_structure(data) is True
