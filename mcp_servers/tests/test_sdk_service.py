"""Unit tests for the HederaSDKService."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.sdk_service import HederaSDKService


class TestHederaSDKService:
    """Test cases for the HederaSDKService class."""

    @pytest.fixture
    def sdk_service(self):
        """Create a HederaSDKService instance for testing."""
        with patch('mcp_servers.app.services.sdk_service.MirrorNodeClient') as mock_client:
            service = HederaSDKService()
            service.client = Mock()
            return service, mock_client

    @pytest.mark.asyncio
    async def test_call_method_success_sync(self, sdk_service):
        """Test successful synchronous method call."""
        service, mock_client = sdk_service
        
        # Mock a synchronous method
        mock_method = Mock(return_value={"transaction_id": "0.0.123@1234567890"})
        service.client.get_transaction = mock_method
        
        result = await service.call_method("get_transaction", transaction_id="0.0.123@1234567890")
        
        assert result["success"] is True
        assert result["data"] == {"transaction_id": "0.0.123@1234567890"}
        assert result["method_called"] == "get_transaction"
        assert result["parameters_used"] == {"transaction_id": "0.0.123@1234567890"}
        mock_method.assert_called_once_with(transaction_id="0.0.123@1234567890")

    @pytest.mark.asyncio
    async def test_call_method_success_async(self, sdk_service):
        """Test successful asynchronous method call."""
        service, mock_client = sdk_service
        
        # Mock an asynchronous method
        mock_method = AsyncMock(return_value={"account_id": "0.0.123"})
        service.client.get_account = mock_method
        
        result = await service.call_method("get_account", account_id="0.0.123")
        
        assert result["success"] is True
        assert result["data"] == {"account_id": "0.0.123"}
        assert result["method_called"] == "get_account"
        assert result["parameters_used"] == {"account_id": "0.0.123"}
        mock_method.assert_called_once_with(account_id="0.0.123")

    @pytest.mark.asyncio
    async def test_call_method_not_found(self, sdk_service):
        """Test calling a non-existent method."""
        service, mock_client = sdk_service
        
        # Create a mock client that explicitly doesn't have the method
        mock_client_instance = Mock(spec=[])
        service.client = mock_client_instance
        
        # Mock get_available_methods to return a list
        service.get_available_methods = Mock(return_value=["get_transaction", "get_account"])
        
        result = await service.call_method("non_existent_method")
        
        assert "error" in result
        assert "Method 'non_existent_method' not found in SDK" in result["error"]
        assert "available_methods" in result

    @pytest.mark.asyncio
    async def test_call_method_not_callable(self, sdk_service):
        """Test calling a non-callable attribute."""
        service, mock_client = sdk_service
        
        # Mock a non-callable attribute
        service.client.some_attribute = "not_callable"
        
        result = await service.call_method("some_attribute")
        
        assert "error" in result
        assert "'some_attribute' is not a callable method" in result["error"]

    @pytest.mark.asyncio
    async def test_call_method_exception(self, sdk_service):
        """Test method call that raises an exception."""
        service, mock_client = sdk_service
        
        # Mock a method that raises an exception
        mock_method = Mock(side_effect=ValueError("Invalid parameter"))
        service.client.get_transaction = mock_method
        
        result = await service.call_method("get_transaction", transaction_id="invalid")
        
        assert "error" in result
        assert "Invalid parameter" in result["error"]
        assert result["error_type"] == "ValueError"
        assert result["method_called"] == "get_transaction"
        assert result["parameters_used"] == {"transaction_id": "invalid"}

    def test_get_available_methods(self, sdk_service):
        """Test getting available methods."""
        service, mock_client = sdk_service
        
        # Create a proper mock client with specific attributes
        mock_client_instance = Mock()
        
        # Set up the mock to have specific methods
        mock_client_instance.get_transaction = Mock()
        mock_client_instance.get_account = Mock()
        mock_client_instance._private_method = Mock()
        mock_client_instance.some_attribute = "not_callable"
        
        # Replace the service's client
        service.client = mock_client_instance
        
        methods = service.get_available_methods()
        
        assert "get_transaction" in methods
        assert "get_account" in methods
        assert "_private_method" not in methods  # Should exclude private methods
        assert "some_attribute" not in methods  # Should exclude non-callable attributes

    def test_get_method_signature_success(self, sdk_service):
        """Test getting method signature successfully."""
        service, mock_client = sdk_service
        
        # Mock a method with parameters
        def mock_method(transaction_id: str, include_children: bool = False):
            return {"transaction_id": transaction_id}
        
        service.client.get_transaction = mock_method
        
        result = service.get_method_signature("get_transaction")
        
        assert result["method_name"] == "get_transaction"
        assert "parameters" in result
        assert "transaction_id" in result["parameters"]
        assert "include_children" in result["parameters"]

    def test_get_method_signature_not_found(self, sdk_service):
        """Test getting signature for non-existent method."""
        service, mock_client = sdk_service
        
        # Mock hasattr to return False for non-existent method
        with patch('builtins.hasattr', return_value=False):
            result = service.get_method_signature("non_existent_method")
        
        assert "error" in result
        assert "Method 'non_existent_method' not found" in result["error"]

    def test_get_method_signature_not_callable(self, sdk_service):
        """Test getting signature for non-callable attribute."""
        service, mock_client = sdk_service
        
        service.client.some_attribute = "not_callable"
        
        result = service.get_method_signature("some_attribute")
        
        assert "error" in result
        assert "'some_attribute' is not callable" in result["error"]