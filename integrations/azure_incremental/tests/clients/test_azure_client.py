from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.clients.azure_client import AzureClient


class TestAzureClient:
    """Test the Azure client functionality."""

    @pytest.fixture
    def mock_client(self) -> AzureClient:
        """Create a mock Azure client."""
        client = AzureClient()
        client._credentials = AsyncMock()
        client.subs_client = AsyncMock()
        client.resource_g_client = AsyncMock()
        return client

    def test_init(self) -> None:
        """Test client initialization."""
        client = AzureClient()
        assert client._credentials is None
        assert client.subs_client is None
        assert client.resource_g_client is None
        assert client._rate_limiter is not None

    @pytest.mark.asyncio
    async def test_context_manager_enter(self, mock_client: AzureClient) -> None:
        """Test context manager enter."""
        with patch("src.clients.azure_client.DefaultAzureCredential") as mock_cred:
            mock_cred.return_value = AsyncMock()

            async with mock_client as client:
                assert client._credentials is not None
                assert client.subs_client is not None
                assert client.resource_g_client is not None

    @pytest.mark.asyncio
    async def test_context_manager_exit(self) -> None:
        """Test context manager exit."""
        # Create a client and manually set up the clients
        client = AzureClient()
        client.subs_client = AsyncMock()
        client.resource_g_client = AsyncMock()

        # Test the exit method directly
        await client.__aexit__(Exception("test"), Exception("test"), None)

        # Verify close was called on both clients
        client.subs_client.close.assert_called_once()
        client.resource_g_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_subscriptions_success(
        self, mock_client: AzureClient
    ) -> None:
        """Test getting all subscriptions successfully."""
        # Mock subscription data
        mock_sub1 = MagicMock()
        mock_sub1.subscription_id = "sub-1"
        mock_sub1.display_name = "Test Sub 1"

        mock_sub2 = MagicMock()
        mock_sub2.subscription_id = "sub-2"
        mock_sub2.display_name = "Test Sub 2"

        # Patch the list method to return an async iterator
        async def async_iter() -> AsyncGenerator[MagicMock, Any]:
            yield mock_sub1
            yield mock_sub2

        mock_client.subs_client.subscriptions.list = lambda: async_iter()  # type: ignore

        subscriptions = await mock_client.get_all_subscriptions()

        assert len(subscriptions) == 2
        assert subscriptions[0].subscription_id == "sub-1"
        assert subscriptions[1].subscription_id == "sub-2"

    @pytest.mark.asyncio
    async def test_get_all_subscriptions_no_client(self) -> None:
        """Test getting subscriptions without initialized client."""
        client = AzureClient()

        with pytest.raises(ValueError, match="Azure client not initialized"):
            await client.get_all_subscriptions()

    @pytest.mark.asyncio
    async def test_run_query_success(self, mock_client: AsyncMock) -> None:
        """Test running a query successfully."""
        # Mock query response
        mock_response = MagicMock()
        mock_response.data = [{"id": "resource-1"}, {"id": "resource-2"}]
        mock_response.skip_token = None

        mock_client.resource_g_client.resources.return_value = mock_response

        query = "resources | where type == 'microsoft.network/virtualnetworks'"
        subscriptions = ["sub-1", "sub-2"]

        results = []
        async for batch in mock_client.run_query(query, subscriptions):
            results.extend(batch)

        assert len(results) == 2
        assert results[0]["id"] == "resource-1"
        assert results[1]["id"] == "resource-2"

    @pytest.mark.asyncio
    async def test_run_query_with_skip_token(self, mock_client: AsyncMock) -> None:
        """Test running a query with skip token for pagination."""
        # Mock first response with skip token
        mock_response1 = MagicMock()
        mock_response1.data = [{"id": "resource-1"}]
        mock_response1.skip_token = "skip-token-1"

        # Mock second response without skip token
        mock_response2 = MagicMock()
        mock_response2.data = [{"id": "resource-2"}]
        mock_response2.skip_token = None

        mock_client.resource_g_client.resources.side_effect = [
            mock_response1,
            mock_response2,
        ]

        query = "resources | where type == 'microsoft.network/virtualnetworks'"
        subscriptions = ["sub-1"]

        results = []
        async for batch in mock_client.run_query(query, subscriptions):
            results.extend(batch)

        assert len(results) == 2
        assert results[0]["id"] == "resource-1"
        assert results[1]["id"] == "resource-2"

        # Verify QueryRequest was called twice with different skip tokens
        assert mock_client.resource_g_client.resources.call_count == 2

    @pytest.mark.asyncio
    async def test_run_query_no_client(self) -> None:
        """Test running query without initialized client."""
        client = AzureClient()

        with pytest.raises(ValueError, match="Azure client not initialized"):
            async for _ in client.run_query("test query", ["sub-1"]):
                pass

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_client: AsyncMock) -> None:
        """Test rate limit handling."""
        # Mock rate limiter to return False (rate limited)
        with patch.object(mock_client._rate_limiter, "consume", return_value=False):
            # Mock query response
            mock_response = MagicMock()
            mock_response.data = [{"id": "resource-1"}]
            mock_response.skip_token = None

            mock_client.resource_g_client.resources.return_value = mock_response

            query = "resources | where type == 'microsoft.network/virtualnetworks'"
            subscriptions = ["sub-1"]

            # This should trigger rate limit handling
            results = []
            async for batch in mock_client.run_query(query, subscriptions):
                results.extend(batch)

            # Verify rate limiter was called
            mock_client._rate_limiter.consume.assert_called()

    @pytest.mark.asyncio
    async def test_handle_rate_limit_success(self, mock_client: AzureClient) -> None:
        """Test rate limit handling when successful."""
        await mock_client._handle_rate_limit(True)
        # Should not sleep when successful

    @pytest.mark.asyncio
    async def test_handle_rate_limit_failure(self, mock_client: AzureClient) -> None:
        """Test rate limit handling when rate limited."""
        with patch("asyncio.sleep") as mock_sleep:
            await mock_client._handle_rate_limit(False)
            mock_sleep.assert_called_once_with(1)
