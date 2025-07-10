from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from src.services.resource_containers import (
    ResourceContainers,
    build_full_sync_container_query,
    build_incremental_container_query,
    build_rg_tag_filter_clause_for_containers,
)
from src.settings import ResourceGroupTagFilters


class TestResourceContainersFiltering:
    """Test the resource containers filtering functionality."""

    def test_build_rg_tag_filter_clause_empty_filters(self) -> None:
        """Test building filter clause with empty filters."""
        filters = ResourceGroupTagFilters()
        result = build_rg_tag_filter_clause_for_containers(filters)
        assert result == ""

    def test_build_rg_tag_filter_clause_include_only(self) -> None:
        """Test building filter clause with include filters only."""
        filters = ResourceGroupTagFilters(include={"Environment": "Production"})
        result = build_rg_tag_filter_clause_for_containers(filters)
        assert "| where " in result
        assert "tostring(tags['Environment']) =~ 'Production'" in result

    def test_build_rg_tag_filter_clause_exclude_only(self) -> None:
        """Test building filter clause with exclude filters only."""
        filters = ResourceGroupTagFilters(exclude={"Temporary": "true"})
        result = build_rg_tag_filter_clause_for_containers(filters)
        assert "| where " in result
        assert "not (" in result
        assert "tostring(tags['Temporary']) =~ 'true'" in result

    def test_build_rg_tag_filter_clause_both_include_and_exclude(self) -> None:
        """Test building filter clause with both include and exclude filters."""
        filters = ResourceGroupTagFilters(
            include={"Environment": "Production"}, exclude={"Temporary": "true"}
        )
        result = build_rg_tag_filter_clause_for_containers(filters)
        assert "| where " in result
        assert " and " in result
        assert "not (" in result

    def test_build_rg_tag_filter_clause_escapes_quotes(self) -> None:
        """Test that quotes in tag values are properly escaped."""
        filters = ResourceGroupTagFilters(include={"Name": "O'Connor"})
        result = build_rg_tag_filter_clause_for_containers(filters)
        assert "O''Connor" in result  # Single quote should be doubled

    def test_build_incremental_container_query(self) -> None:
        """Test building incremental container query."""
        with patch("src.services.resource_containers.app_settings") as mock_settings:
            mock_settings.CHANGE_WINDOW_MINUTES = 15
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            result = build_incremental_container_query()

            assert "resourcecontainerchanges" in result
            assert "ago(15m)" in result
            assert "resourcecontainers" in result

    def test_build_full_sync_container_query(self) -> None:
        """Test building full sync container query."""
        with patch("src.services.resource_containers.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            result = build_full_sync_container_query()

            assert "resourcecontainers" in result
            assert "resourceId=tolower(id)" in result


class TestResourceContainersService:
    """Test the ResourceContainers service."""

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
    def resource_containers(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> ResourceContainers:
        """Create a ResourceContainers service instance."""
        return ResourceContainers(mock_azure_client, mock_port_client)

    def test_init_with_filters(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> None:
        """Test initialization with tag filters."""
        with patch("src.services.resource_containers.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters(include={"Environment": "Production"})
            )

            service = ResourceContainers(mock_azure_client, mock_port_client)
            assert service.azure_client == mock_azure_client
            assert service.port_client == mock_port_client

    def test_init_without_filters(
        self, mock_azure_client: AsyncMock, mock_port_client: AsyncMock
    ) -> None:
        """Test initialization without tag filters."""
        with patch("src.services.resource_containers.app_settings") as mock_settings:
            mock_settings.get_resource_group_tag_filters.return_value = (
                ResourceGroupTagFilters()
            )

            service = ResourceContainers(mock_azure_client, mock_port_client)
            assert service.azure_client == mock_azure_client
            assert service.port_client == mock_port_client

    @pytest.mark.asyncio
    async def test_sync_full_success(
        self,
        resource_containers: ResourceContainers,
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
                    "resourceId": "/subscriptions/sub/resourcegroups/rg1",
                    "name": "rg1",
                    "type": "microsoft.resources/subscriptions/resourcegroups",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg1",
                },
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg2",
                    "name": "rg2",
                    "type": "microsoft.resources/subscriptions/resourcegroups",
                    "location": "westus",
                    "tags": {"Environment": "Development"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg2",
                },
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1", "sub-2"]

        await resource_containers.sync_full(subscriptions)

        # Verify Port client was called for each resource
        assert mock_port_client.send_webhook_data.call_count == 2

        # Verify the calls were made with correct data
        calls = mock_port_client.send_webhook_data.call_args_list
        assert calls[0][1]["operation"] == "upsert"
        assert calls[0][1]["type"] == "resourceContainer"
        assert calls[1][1]["operation"] == "upsert"
        assert calls[1][1]["type"] == "resourceContainer"

    @pytest.mark.asyncio
    async def test_sync_full_empty_results(
        self,
        resource_containers: ResourceContainers,
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

        await resource_containers.sync_full(subscriptions)

        # Should not call Port client
        mock_port_client.send_webhook_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_incremental_success(
        self,
        resource_containers: ResourceContainers,
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
                    "resourceId": "/subscriptions/sub/resourcegroups/rg1",
                    "name": "rg1",
                    "type": "microsoft.resources/subscriptions/resourcegroups",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg1",
                    "changeType": "Create",
                },
                {
                    "resourceId": "/subscriptions/sub/resourcegroups/rg2",
                    "name": "rg2",
                    "type": "microsoft.resources/subscriptions/resourcegroups",
                    "location": "westus",
                    "tags": {"Environment": "Development"},
                    "subscriptionId": "sub",
                    "resourceGroup": "rg2",
                    "changeType": "Delete",
                },
            ]

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1", "sub-2"]

        await resource_containers.sync_incremental(subscriptions)

        # Verify Port client was called for each resource
        assert mock_port_client.send_webhook_data.call_count == 2

        # Verify the calls were made with correct data
        calls = mock_port_client.send_webhook_data.call_args_list
        assert calls[0][1]["operation"] == "upsert"  # Create
        assert calls[0][1]["type"] == "resourceContainer"
        assert calls[1][1]["operation"] == "delete"  # Delete
        assert calls[1][1]["type"] == "resourceContainer"

    @pytest.mark.asyncio
    async def test_sync_incremental_empty_results(
        self,
        resource_containers: ResourceContainers,
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

        await resource_containers.sync_incremental(subscriptions)

        # Should not call Port client
        mock_port_client.send_webhook_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_batch_processing(
        self,
        resource_containers: ResourceContainers,
        mock_azure_client: AsyncMock,
        mock_port_client: AsyncMock,
    ) -> None:
        """Test that resources are processed in batches."""
        # Create more than 100 resources to test batching
        resources: List[Dict[str, Any]] = []
        for i in range(150):
            resources.append(
                {
                    "resourceId": f"/subscriptions/sub/resourcegroups/rg{i}",
                    "name": f"rg{i}",
                    "type": "microsoft.resources/subscriptions/resourcegroups",
                    "location": "eastus",
                    "tags": {"Environment": "Production"},
                    "subscriptionId": "sub",
                    "resourceGroup": f"rg{i}",
                }
            )

        async def mock_run_query(
            query: str, subscriptions: List[str]
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield resources

        mock_azure_client.run_query = lambda *a, **kw: mock_run_query(*a, **kw)

        subscriptions: List[str] = ["sub-1"]

        await resource_containers.sync_full(subscriptions)

        # Should process in two batches (100 + 50)
        assert mock_port_client.send_webhook_data.call_count == 150
