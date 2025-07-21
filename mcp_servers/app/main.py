from typing import Any, Dict, List, Union
from datetime import datetime, timezone
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
    return get_sdk_service().get_available_methods()

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
    return get_sdk_service().get_method_signature(method_name)

@mcp.tool()
async def health_check() -> Dict[str, str]:
    """
    Check the health status of the Hedera Mirror Node MCP Server.
    
    Returns:
        Dict with status information
    """
    return {"status": "ok", "service": "HederaMirrorNode"}

@mcp.tool()
async def convert_timestamp(timestamp: Union[str, int, float]) -> Dict[str, Any]:
    """
    Convert Unix timestamp to human-readable date format.
    
    Handles both regular Unix timestamps (seconds since epoch) and Hedera timestamps 
    with nanosecond precision (seconds.nanoseconds format).
    
    Args:
        timestamp: Unix timestamp (can be int, float, or string format)
        
    Returns:
        Dict containing original timestamp, converted date, and metadata
        
    Example usage:
        - convert_timestamp(1752127198.022577) -> "2025-07-17 14:49:58 UTC"
        - convert_timestamp("1752127198") -> "2025-07-17 14:49:58 UTC"
    """
    try:
        # Convert input to string for consistent processing
        timestamp_str = str(timestamp)
        
        # Handle different timestamp formats
        if '.' in timestamp_str:
            # Hedera format: seconds.nanoseconds
            seconds_str = timestamp_str.split('.')[0]
            nanoseconds_str = timestamp_str.split('.')[1]
            unix_seconds = int(seconds_str)
            nanoseconds = int(nanoseconds_str.ljust(9, '0')[:9])  # Pad/truncate to 9 digits
        else:
            # Regular Unix timestamp
            unix_seconds = int(float(timestamp_str))
            nanoseconds = 0
        
        # Convert to datetime object
        dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
        
        # Format outputs
        human_readable = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        iso_format = dt.isoformat()
        
        return {
            "original_timestamp": timestamp,
            "unix_seconds": unix_seconds,
            "nanoseconds": nanoseconds,
            "human_readable": human_readable,
            "iso_format": iso_format,
            "success": True
        }
        
    except (ValueError, OverflowError) as e:
        return {
            "original_timestamp": timestamp,
            "error": f"Invalid timestamp format: {str(e)}",
            "success": False
        }


