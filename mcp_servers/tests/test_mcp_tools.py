"""Unit tests for the MCP tools."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.main import call_sdk_method, get_available_methods, get_method_signature, health_check


class TestMCPTools:
    """Test cases for the MCP tools."""

    @pytest.fixture
    def mock_sdk_service(self):
        """Create a mock SDK service for testing."""
        with patch('app.main.sdk_service') as mock_service:
            yield mock_service

    @pytest.mark.asyncio
    async def test_call_sdk_method_success(self, mock_sdk_service):
        """Test successful SDK method call through MCP tool."""
        # Mock the SDK service call_method
        mock_sdk_service.call_method = AsyncMock(return_value={
            "success": True,
            "data": {"transaction_id": "0.0.123@1234567890"},
            "method_called": "get_transaction",
            "parameters_used": {"transaction_id": "0.0.123@1234567890"}
        })
        
        result = await call_sdk_method("get_transaction", transaction_id="0.0.123@1234567890")
        
        assert result["success"] is True
        assert result["data"] == {"transaction_id": "0.0.123@1234567890"}
        assert result["method_called"] == "get_transaction"
        mock_sdk_service.call_method.assert_called_once_with(
            "get_transaction", 
            transaction_id="0.0.123@1234567890"
        )

    @pytest.mark.asyncio
    async def test_call_sdk_method_error(self, mock_sdk_service):
        """Test SDK method call with error through MCP tool."""
        # Mock the SDK service call_method with error
        mock_sdk_service.call_method = AsyncMock(return_value={
            "error": "Method 'invalid_method' not found in SDK",
            "available_methods": ["get_transaction", "get_account"]
        })
        
        result = await call_sdk_method("invalid_method")
        
        assert "error" in result
        assert "Method 'invalid_method' not found in SDK" in result["error"]
        assert "available_methods" in result
        mock_sdk_service.call_method.assert_called_once_with("invalid_method")

    @pytest.mark.asyncio
    async def test_call_sdk_method_with_multiple_params(self, mock_sdk_service):
        """Test SDK method call with multiple parameters."""
        # Mock the SDK service call_method
        mock_sdk_service.call_method = AsyncMock(return_value={
            "success": True,
            "data": {"account_id": "0.0.123", "transactions": []},
            "method_called": "get_account_transactions",
            "parameters_used": {"account_id": "0.0.123", "limit": 10, "order": "desc"}
        })
        
        result = await call_sdk_method(
            "get_account_transactions", 
            account_id="0.0.123", 
            limit=10, 
            order="desc"
        )
        
        assert result["success"] is True
        assert result["method_called"] == "get_account_transactions"
        mock_sdk_service.call_method.assert_called_once_with(
            "get_account_transactions",
            account_id="0.0.123",
            limit=10,
            order="desc"
        )

    @pytest.mark.asyncio
    async def test_get_available_methods(self, mock_sdk_service):
        """Test getting available methods through MCP tool."""
        # Mock the SDK service get_available_methods
        mock_sdk_service.get_available_methods = Mock(return_value=[
            "get_transaction", "get_account", "get_token", "get_topic"
        ])
        
        result = await get_available_methods()
        
        assert isinstance(result, list)
        assert "get_transaction" in result
        assert "get_account" in result
        assert "get_token" in result
        assert "get_topic" in result
        mock_sdk_service.get_available_methods.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_method_signature_success(self, mock_sdk_service):
        """Test getting method signature successfully through MCP tool."""
        # Mock the SDK service get_method_signature
        mock_sdk_service.get_method_signature = Mock(return_value={
            "method_name": "get_transaction",
            "parameters": {
                "transaction_id": {
                    "annotation": "<class 'str'>",
                    "default": None,
                    "kind": "POSITIONAL_OR_KEYWORD"
                },
                "include_children": {
                    "annotation": "<class 'bool'>",
                    "default": False,
                    "kind": "POSITIONAL_OR_KEYWORD"
                }
            },
            "return_annotation": None
        })
        
        result = await get_method_signature("get_transaction")
        
        assert result["method_name"] == "get_transaction"
        assert "parameters" in result
        assert "transaction_id" in result["parameters"]
        assert "include_children" in result["parameters"]
        mock_sdk_service.get_method_signature.assert_called_once_with("get_transaction")

    @pytest.mark.asyncio
    async def test_get_method_signature_error(self, mock_sdk_service):
        """Test getting method signature with error through MCP tool."""
        # Mock the SDK service get_method_signature with error
        mock_sdk_service.get_method_signature = Mock(return_value={
            "error": "Method 'invalid_method' not found"
        })
        
        result = await get_method_signature("invalid_method")
        
        assert "error" in result
        assert "Method 'invalid_method' not found" in result["error"]
        mock_sdk_service.get_method_signature.assert_called_once_with("invalid_method")

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check MCP tool."""
        result = await health_check()
        
        assert result["status"] == "ok"
        assert result["service"] == "HederaMirrorNode"