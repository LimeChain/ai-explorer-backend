from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

from .services.sdk_service import HederaSDKService

# Initialize the FastMCP server for Hedera Mirror Node
mcp = FastMCP("HederaMirrorNode")
sdk_service = None

def get_sdk_service():
    global sdk_service
    if sdk_service is None:
        sdk_service = HederaSDKService()
    return sdk_service

@mcp.tool()
async def call_sdk_method(method_name: str, **kwargs) -> Dict[str, Any]:
    """
    Call any method from the Hedera Mirror Node SDK dynamically.
    
    This tool allows the agent to call any public method available in the SDK.
    The agent should refer to the SDK documentation to determine which method
    to call and what parameters to pass.
    
    Args:
        method_name: The name of the SDK method to call (e.g., 'get_transaction', 'get_account')
        **kwargs: Parameters to pass to the method as specified in the SDK documentation
        
    Returns:
        Dict containing the method result, error information, or success status
        
    Example usage:
        - call_sdk_method(method_name="get_transaction", transaction_id="0.0.123@1234567890")
        - call_sdk_method(method_name="get_account", account_id="0.0.123")
    """
    return await get_sdk_service().call_method(method_name, **kwargs)

@mcp.tool()
async def get_available_methods() -> List[str]:
    """
    Get a list of all available public methods in the Hedera Mirror Node SDK.
    
    This tool helps the agent discover what methods are available to call.
    
    Returns:
        List of available method names
    """
    return get_sdk_service.get_available_methods()

@mcp.tool()
async def get_method_signature(method_name: str) -> Dict[str, Any]:
    """
    Get the signature information for a specific SDK method.
    
    This tool helps the agent understand what parameters a method expects
    and what types they should be.
    
    Args:
        method_name: The name of the method to inspect
        
    Returns:
        Dict containing parameter information, types, and defaults
    """
    return get_sdk_service.get_method_signature(method_name)

@mcp.tool()
async def health_check() -> Dict[str, str]:
    """
    Check the health status of the Hedera Mirror Node MCP Server.
    
    Returns:
        Dict with status information
    """
    return {"status": "ok", "service": "HederaMirrorNode"}


