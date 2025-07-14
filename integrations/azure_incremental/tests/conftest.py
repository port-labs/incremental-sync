import os
import sys
from pathlib import Path

# Set test environment variables BEFORE any imports to prevent validation errors
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("PORT_WEBHOOK_INGEST_URL", "https://test-port.com/webhook")
os.environ.setdefault("PORT_WEBHOOK_SECRET", "test-secret")

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from src.clients.azure_client import AzureClient
from src.clients.port import PortClient
from src.services.resource_containers import ResourceContainers
from src.services.resources import Resources


def pytest_configure(config: Any) -> None:
    """Configure pytest with test environment variables."""
    # Environment variables are already set at the top of the file
    pass


@pytest.fixture(autouse=True)
def setup_test_environment() -> None:
    """Set up test environment variables."""
    # Environment variables are already set at the top of the file
    pass


@pytest.fixture
def mock_azure_client() -> AsyncMock:
    """Create a mock Azure client."""
    client: AsyncMock = AsyncMock(spec=AzureClient)
    client.run_query = AsyncMock()
    client.get_all_subscriptions = AsyncMock()
    return client


@pytest.fixture
def mock_port_client() -> AsyncMock:
    """Create a mock Port client."""
    client: AsyncMock = AsyncMock(spec=PortClient)
    client.send_webhook_data = AsyncMock()
    return client


@pytest.fixture
def resources_service(
    mock_azure_client: AsyncMock, mock_port_client: AsyncMock
) -> Resources:
    """Create a Resources instance with mocked dependencies."""
    return Resources(mock_azure_client, mock_port_client)


@pytest.fixture
def resource_containers_service(
    mock_azure_client: AsyncMock, mock_port_client: AsyncMock
) -> ResourceContainers:
    """Create a ResourceContainers instance with mocked dependencies."""
    return ResourceContainers(mock_azure_client, mock_port_client)


@pytest.fixture
def sample_resource_data() -> Dict[str, Any]:
    """Sample resource data for testing."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "tags": {"Environment": "Production", "Team": "Platform"},
        "properties": {
            "vmId": "test-vm-id",
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        },
    }


@pytest.fixture
def sample_container_data() -> Dict[str, Any]:
    """Sample resource container data for testing."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg",
        "name": "test-rg",
        "type": "Microsoft.Resources/resourceGroups",
        "location": "eastus",
        "tags": {"Environment": "Production", "Team": "Platform"},
        "properties": {
            "provisioningState": "Succeeded",
        },
    }
