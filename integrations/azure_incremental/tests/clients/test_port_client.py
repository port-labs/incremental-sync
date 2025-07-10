"""Tests for the Port client."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.clients.port import PortClient


class TestPortClient:
    """Test the Port client functionality."""

    @pytest.fixture
    def mock_http_client(self) -> AsyncMock:
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def port_client(self, mock_http_client: AsyncMock) -> PortClient:
        """Create a Port client with mock HTTP client."""
        return PortClient(mock_http_client)

    def test_init(self, mock_http_client: AsyncMock) -> None:
        """Test client initialization."""
        client = PortClient(mock_http_client)
        assert client.http_client == mock_http_client
        assert client.webhook_ingest_url is not None
        assert client.webhook_secret is not None
        assert client.semaphore is not None

    @pytest.mark.asyncio
    async def test_send_webhook_data_success(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test successful webhook data sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        data = {"id": "test-resource", "name": "Test Resource"}

        await port_client.send_webhook_data(
            data=data, id="test-id", operation="upsert", type="resource"
        )

        # Verify HTTP client was called
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == port_client.webhook_ingest_url

        # Verify request body
        request_body = call_args[1]["json"]
        assert request_body["data"] == data
        assert request_body["operation"] == "upsert"
        assert request_body["type"] == "resource"

    @pytest.mark.asyncio
    async def test_send_webhook_data_with_retries(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test webhook data sending with retries on failure."""
        # Mock failed response first, then success
        mock_failed_response = MagicMock()
        mock_failed_response.raise_for_status.side_effect = httpx.HTTPError(
            "Connection error"
        )

        mock_success_response = MagicMock()
        mock_success_response.raise_for_status.return_value = None

        mock_http_client.post.side_effect = [
            mock_failed_response,
            mock_success_response,
        ]

        data = {"id": "test-resource", "name": "Test Resource"}

        await port_client.send_webhook_data(
            data=data, id="test-id", operation="upsert", type="resource"
        )

        # Verify HTTP client was called twice (retry)
        assert mock_http_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_webhook_data_max_retries_exceeded(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test webhook data sending when max retries are exceeded."""
        # Mock failed responses
        mock_failed_response = MagicMock()
        mock_failed_response.raise_for_status.side_effect = httpx.HTTPError(
            "Connection error"
        )
        mock_http_client.post.return_value = mock_failed_response

        data = {"id": "test-resource", "name": "Test Resource"}

        # Should not raise exception, just log error
        await port_client.send_webhook_data(
            data=data, id="test-id", operation="upsert", type="resource"
        )

        # Verify HTTP client was called 3 times (initial + 2 retries)
        assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_webhook_data_concurrent_requests(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test concurrent webhook data sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        # Send multiple concurrent requests
        tasks = []
        for i in range(5):
            data = {"id": f"test-resource-{i}", "name": f"Test Resource {i}"}
            task = port_client.send_webhook_data(
                data=data, id=f"test-id-{i}", operation="upsert", type="resource"
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify all requests were made
        assert mock_http_client.post.call_count == 5

    @pytest.mark.asyncio
    async def test_send_webhook_data_semaphore_limits(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test that semaphore limits concurrent requests."""

        # Mock slow response
        async def slow_response(*args: Any, **kwargs: Any) -> httpx.Response:
            await asyncio.sleep(0.1)
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_http_client.post.side_effect = slow_response

        # Send more requests than semaphore limit
        tasks = []
        for i in range(30):  # More than semaphore limit of 25
            data = {"id": f"test-resource-{i}", "name": f"Test Resource {i}"}
            task = port_client.send_webhook_data(
                data=data, id=f"test-id-{i}", operation="upsert", type="resource"
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Verify all requests were made
        assert mock_http_client.post.call_count == 30

    @pytest.mark.asyncio
    async def test_send_webhook_data_different_operations(
        self, port_client: PortClient, mock_http_client: AsyncMock
    ) -> None:
        """Test sending different types of operations."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_http_client.post.return_value = mock_response

        data = {"id": "test-resource", "name": "Test Resource"}

        # Test upsert operation
        await port_client.send_webhook_data(
            data=data, id="test-id", operation="upsert", type="resource"
        )

        # Test delete operation
        await port_client.send_webhook_data(
            data=data, id="test-id", operation="delete", type="resource"
        )

        # Verify both requests were made with correct operations
        assert mock_http_client.post.call_count == 2
        calls = mock_http_client.post.call_args_list

        assert calls[0][1]["json"]["operation"] == "upsert"
        assert calls[1][1]["json"]["operation"] == "delete"
