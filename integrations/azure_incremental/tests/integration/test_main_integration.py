from typing import Any, Optional, Sequence, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import main


class TestMainIntegration:
    """Integration tests for the main module."""

    ENV_VARS_BASE: dict[str, str] = {
        "AZURE_CLIENT_ID": "test-client-id",
        "AZURE_CLIENT_SECRET": "test-client-secret",
        "AZURE_TENANT_ID": "test-tenant-id",
        "PORT_WEBHOOK_INGEST_URL": "https://test-port.com/webhook",
        "PORT_WEBHOOK_SECRET": "test-secret",
    }

    def _mock_azure_client(
        self,
        mock_azure_client: Any,
        subscriptions: Optional[Sequence[Any]] = None,
        raise_exc: Optional[Exception] = None,
    ) -> AsyncMock:
        mock_azure_instance = AsyncMock()
        if raise_exc:
            mock_azure_client.return_value.__aenter__.side_effect = raise_exc
        else:
            mock_azure_client.return_value.__aenter__.return_value = mock_azure_instance
            if subscriptions is not None:
                mock_azure_instance.get_all_subscriptions.return_value = subscriptions
        return mock_azure_instance

    def _mock_services(
        self, mock_containers: Any, mock_resources: Any
    ) -> Tuple[AsyncMock, AsyncMock]:
        mock_containers_instance = AsyncMock()
        mock_resources_instance = AsyncMock()
        mock_containers.return_value = mock_containers_instance
        mock_resources.return_value = mock_resources_instance
        return mock_containers_instance, mock_resources_instance

    @pytest.mark.asyncio
    @patch("src.main.AzureClient")
    @patch("src.main.PortClient")
    @patch("src.main.ResourceContainers")
    @patch("src.main.Resources")
    async def test_main_success_incremental_mode(
        self,
        mock_resources: Any,
        mock_containers: Any,
        mock_port_client: Any,
        mock_azure_client: Any,
    ) -> None:
        """Test successful main execution in incremental mode."""
        env: dict[str, str] = {**self.ENV_VARS_BASE, "SYNC_MODE": "incremental"}
        with patch.dict("os.environ", env):
            mock_sub1 = MagicMock()
            mock_sub1.subscription_id = "sub-1"
            mock_sub2 = MagicMock()
            mock_sub2.subscription_id = "sub-2"
            self._mock_azure_client(mock_azure_client, [mock_sub1, mock_sub2])
            mock_containers_instance, mock_resources_instance = self._mock_services(
                mock_containers, mock_resources
            )

            await main()

            mock_azure_client.assert_called_once()
            mock_containers.assert_called_once()
            mock_resources.assert_called_once()
            mock_containers_instance.sync_incremental.assert_called_once()
            mock_resources_instance.sync_incremental.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.AzureClient")
    @patch("src.main.PortClient")
    @patch("src.main.ResourceContainers")
    @patch("src.main.Resources")
    @patch("src.main.app_settings")
    async def test_main_success_full_mode(
        self,
        mock_app_settings: Any,
        mock_resources: Any,
        mock_containers: Any,
        mock_port_client: Any,
        mock_azure_client: Any,
    ) -> None:
        """Test successful main execution in full mode."""
        mock_app_settings.SYNC_MODE.value = "full"
        mock_app_settings.SUBSCRIPTION_BATCH_SIZE = 10
        env: dict[str, str] = {**self.ENV_VARS_BASE, "SYNC_MODE": "full"}
        with patch.dict("os.environ", env):
            mock_sub1 = MagicMock()
            mock_sub1.subscription_id = "sub-1"
            self._mock_azure_client(mock_azure_client, [mock_sub1])
            mock_containers_instance, mock_resources_instance = self._mock_services(
                mock_containers, mock_resources
            )

            await main()

            mock_containers_instance.sync_full.assert_called_once()
            mock_resources_instance.sync_full.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.AzureClient")
    async def test_main_no_subscriptions(self, mock_azure_client: Any) -> None:
        """Test main execution when no subscriptions are found."""
        env: dict[str, str] = dict(self.ENV_VARS_BASE)
        with patch.dict("os.environ", env):
            mock_azure_instance = self._mock_azure_client(mock_azure_client, [])
            await main()
            mock_azure_instance.get_all_subscriptions.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.AzureClient")
    async def test_main_azure_client_error(self, mock_azure_client: Any) -> None:
        """Test main execution when Azure client raises an error."""
        env: dict[str, str] = dict(self.ENV_VARS_BASE)
        with patch.dict("os.environ", env):
            self._mock_azure_client(
                mock_azure_client, raise_exc=Exception("Azure connection failed")
            )
            with pytest.raises(Exception, match="Azure connection failed"):
                await main()
            mock_azure_client.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.main.AzureClient")
    @patch("src.main.PortClient")
    @patch("src.main.ResourceContainers")
    @patch("src.main.Resources")
    @patch("src.main.app_settings")
    async def test_main_with_resource_types(
        self,
        mock_app_settings: Any,
        mock_resources: Any,
        mock_containers: Any,
        mock_port_client: Any,
        mock_azure_client: Any,
    ) -> None:
        """Test main execution with specific resource types."""

        class DummySyncMode:
            value = "incremental"

            def __eq__(self, other: object) -> bool:
                return other == "incremental"

        mock_app_settings.SYNC_MODE = DummySyncMode()
        mock_app_settings.RESOURCE_TYPES = [
            "microsoft.network/virtualnetworks",
            "microsoft.keyvault/vaults",
        ]
        mock_app_settings.SUBSCRIPTION_BATCH_SIZE = 10

        env: dict[str, str] = {
            **self.ENV_VARS_BASE,
            "SYNC_MODE": "incremental",
            "RESOURCE_TYPES": '["microsoft.network/virtualnetworks","microsoft.keyvault/vaults"]',
        }
        with patch.dict("os.environ", env):
            mock_sub1 = MagicMock()
            mock_sub1.subscription_id = "sub-1"
            self._mock_azure_client(mock_azure_client, [mock_sub1])
            mock_containers_instance, mock_resources_instance = self._mock_services(
                mock_containers, mock_resources
            )

            await main()

            mock_resources_instance.sync_incremental.assert_called_once()
            call_args = mock_resources_instance.sync_incremental.call_args
            assert call_args[0][1] == [
                "microsoft.network/virtualnetworks",
                "microsoft.keyvault/vaults",
            ]
