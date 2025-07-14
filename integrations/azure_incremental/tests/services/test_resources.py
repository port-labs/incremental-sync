from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from src.services.resources import (
    Resources,
    build_full_sync_query,
    build_incremental_query,
    build_rg_tag_filter_clause,
)
from src.settings import ResourceGroupTagFilters


class TestResourcesFiltering:
    """Test the resources filtering functionality."""

    def test_build_rg_tag_filter_clause_empty_filters(self) -> None:
        """Test building filter clause with empty filters."""
        filters = ResourceGroupTagFilters()
        result = build_rg_tag_filter_clause(filters)
        assert result == ""

    def test_build_rg_tag_filter_clause_include_only(self) -> None:
        """Test building filter clause with include filters only."""
        filters = ResourceGroupTagFilters(include={"Environment": "Production"})
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert "tostring(rgTags['Environment']) =~ 'Production'" in result

    def test_build_rg_tag_filter_clause_exclude_only(self) -> None:
        """Test building filter clause with exclude filters only."""
        filters = ResourceGroupTagFilters(exclude={"Temporary": "true"})
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert "not (" in result
        assert "tostring(rgTags['Temporary']) =~ 'true'" in result

    def test_build_rg_tag_filter_clause_both_include_and_exclude(self) -> None:
        """Test building filter clause with both include and exclude filters."""
        filters = ResourceGroupTagFilters(
            include={"Environment": "Production"}, exclude={"Temporary": "true"}
        )
        result = build_rg_tag_filter_clause(filters)
        assert "| where " in result
        assert " and " in result
        assert "not (" in result

    def test_build_rg_tag_filter_clause_escapes_quotes(self) -> None:
        """Test that quotes in tag values are properly escaped."""
        filters = ResourceGroupTagFilters(include={"Name": "O'Connor"})
        result = build_rg_tag_filter_clause(filters)
        assert "O''Connor" in result  # Single quote should be doubled

    def test_build_incremental_query_no_resource_types(self) -> None:
        """Test building incremental query without resource types."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.CHANGE_WINDOW_MINUTES = 15
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            result = build_incremental_query()

            assert "resourcechanges" in result
            assert "ago(15m)" in result
            assert "resources" in result
            assert "resourcecontainers" in result

    def test_build_incremental_query_with_resource_types(self) -> None:
        """Test building incremental query with resource types."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.CHANGE_WINDOW_MINUTES = 15
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            resource_types = [
                "microsoft.network/virtualnetworks",
                "microsoft.keyvault/vaults",
            ]
            result = build_incremental_query(resource_types)

            assert "resourcechanges" in result
            assert "ago(15m)" in result
            assert "type == 'microsoft.network/virtualnetworks'" in result
            assert "type == 'microsoft.keyvault/vaults'" in result

    def test_build_full_sync_query_no_resource_types(self) -> None:
        """Test building full sync query without resource types."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            result = build_full_sync_query()

            assert "resources" in result
            assert "resourceId=tolower(id)" in result
            assert "resourcecontainers" in result

    def test_build_full_sync_query_with_resource_types(self) -> None:
        """Test building full sync query with resource types."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            resource_types = ["microsoft.network/virtualnetworks"]
            result = build_full_sync_query(resource_types)

            assert "resources" in result
            assert "type == 'microsoft.network/virtualnetworks'" in result


class TestResourcesService:
    """Test the Resources service."""

    @pytest.fixture
    def mock_azure_client(self) -> AsyncMock:
        """Create a mock Azure client."""
        client = AsyncMock()
        client.run_query = AsyncMock()
        return client

    @pytest.fixture
    def mock_port_client(self) -> AsyncMock:
        """Create a mock Port client."""
        client = AsyncMock()
        client.send_webhook_data = AsyncMock()
        return client

    @pytest.fixture
    def resources_service(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> Resources:
        """Create a Resources service instance."""
        return Resources(mock_azure_client, mock_port_client)

    def test_init_with_filters(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> None:
        """Test initialization with tag filters."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters(include={"Environment": "Production"})
            )

            service = Resources(mock_azure_client, mock_port_client)
            assert service.azure_client == mock_azure_client
            assert service.port_client == mock_port_client

    def test_init_without_filters(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> None:
        """Test initialization without tag filters."""
        with patch("src.services.resources.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            service = Resources(mock_azure_client, mock_port_client)
            assert service.azure_client == mock_azure_client
            assert service.port_client == mock_port_client

    @pytest.mark.asyncio
    async def test_sync_full_success(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test successful full sync."""

        # Mock Azure query results as an async generator
        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet1",
                    "name": "vnet1",
                    "type": "microsoft.network/virtualnetworks",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Production", "Team": "Platform"},
                },
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.keyvault/vaults/kv1",
                    "name": "kv1",
                    "type": "microsoft.keyvault/vaults",
                    "location": "westus",
                    "tags": {"Environment": "Development"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Development"},
                },
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1", "sub-2"]

        await resources_service.sync_full(subscriptions)

        # Verify Port client was called for each resource
        assert mock_port_client.send_webhook_data.call_count == 2

        # Verify the calls were made with correct data
        calls = mock_port_client.send_webhook_data.call_args_list
        assert calls[0][1]["operation"] == "upsert"
        assert calls[0][1]["type"] == "resource"
        assert calls[1][1]["operation"] == "upsert"
        assert calls[1][1]["type"] == "resource"

    @pytest.mark.asyncio
    async def test_sync_full_with_resource_types(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test full sync with specific resource types."""

        # Mock Azure query results as an async generator
        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet1",
                    "name": "vnet1",
                    "type": "microsoft.network/virtualnetworks",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Production"},
                }
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]
        resource_types: List[str] = ["microsoft.network/virtualnetworks"]

        await resources_service.sync_full(subscriptions, resource_types)

        # Verify Port client was called
        assert mock_port_client.send_webhook_data.call_count == 1

        # Verify the call was made with correct data
        call = mock_port_client.send_webhook_data.call_args
        assert call[1]["operation"] == "upsert"
        assert call[1]["type"] == "resource"

    @pytest.mark.asyncio
    async def test_sync_full_empty_results(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test full sync with empty results."""

        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]

        await resources_service.sync_full(subscriptions)

        # Should not call Port client
        mock_port_client.send_webhook_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_incremental_success(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test successful incremental sync."""

        # Mock Azure query results as an async generator
        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet1",
                    "name": "vnet1",
                    "type": "microsoft.network/virtualnetworks",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Production"},
                    "changeType": "Create",
                },
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.keyvault/vaults/kv1",
                    "name": "kv1",
                    "type": "microsoft.keyvault/vaults",
                    "location": "westus",
                    "tags": {"Environment": "Development"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Development"},
                    "changeType": "Delete",
                },
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1", "sub-2"]

        await resources_service.sync_incremental(subscriptions)

        # Verify Port client was called for each resource
        assert mock_port_client.send_webhook_data.call_count == 2

        # Verify the calls were made with correct data
        calls = mock_port_client.send_webhook_data.call_args_list
        assert calls[0][1]["operation"] == "upsert"  # Create
        assert calls[0][1]["type"] == "resource"
        assert calls[1][1]["operation"] == "delete"  # Delete
        assert calls[1][1]["type"] == "resource"

    @pytest.mark.asyncio
    async def test_sync_incremental_with_resource_types(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test incremental sync with specific resource types."""

        # Mock Azure query results as an async generator
        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet1",
                    "name": "vnet1",
                    "type": "microsoft.network/virtualnetworks",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Production"},
                    "changeType": "Create",
                }
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]
        resource_types: List[str] = ["microsoft.network/virtualnetworks"]

        await resources_service.sync_incremental(subscriptions, resource_types)

        # Verify Port client was called
        assert mock_port_client.send_webhook_data.call_count == 1

        # Verify the call was made with correct data
        call = mock_port_client.send_webhook_data.call_args
        assert call[1]["operation"] == "upsert"
        assert call[1]["type"] == "resource"

    @pytest.mark.asyncio
    async def test_sync_incremental_empty_results(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test incremental sync with empty results."""

        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]

        await resources_service.sync_incremental(subscriptions)

        # Should not call Port client
        mock_port_client.send_webhook_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_batch_processing(
        self,
        resources_service: Resources,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test that resources are processed in batches."""
        # Create more than 100 resources to test batching
        resources: List[Dict[str, Any]] = []
        for i in range(150):
            resources.append(
                {
                    "resourceId": f"/subscriptions/sub/resourcegroups/rg/providers/microsoft.network/virtualnetworks/vnet{i}",
                    "name": f"vnet{i}",
                    "type": "microsoft.network/virtualnetworks",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg",
                    "rgTags": {"Environment": "Production"},
                }
            )

        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield resources

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]

        await resources_service.sync_full(subscriptions)

        # Should process in two batches (100 + 50)
        assert mock_port_client.send_webhook_data.call_count == 150
