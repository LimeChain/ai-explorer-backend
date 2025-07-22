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
async def calculate_hbar_value(hbar_amount: Union[str, int, float], timestamp: Union[str, int, float] = None) -> Dict[str, Any]:
    """
    Calculate the USD value of HBAR tokens using current exchange rates.
    
    This tool fetches the current HBAR exchange rate and calculates the equivalent
    USD value for the specified amount in tinybars. 1 HBAR = 100,000,000 tinybars.
    
    Args:
        hbar_amount: The amount in tinybars to calculate the USD value for (supports large integers)
        timestamp: Optional Unix timestamp (epoch) to get historical exchange rates
        
    Returns:
        Dict containing tinybar amount, HBAR amount, USD equivalent, exchange rate info, and calculation timestamp
        
    Example usage:
        - calculate_hbar_value(hbar_amount=150000000000) -> calculates USD value for 1,500 tinybars (0.000015 HBAR)
        - calculate_hbar_value(hbar_amount="1000000000000") -> calculates USD value for large tinybar amounts
        - calculate_hbar_value(hbar_amount=3000000000000, timestamp=1705276800) -> historical calculation for epoch timestamp
    """
    try:
        # Get current exchange rate using the SDK
        exchange_rate_params = {}
        if timestamp:
            exchange_rate_params["timestamp"] = str(timestamp)
            
        exchange_rate_result = await get_sdk_service().call_method(
            "get_network_exchange_rate", **exchange_rate_params
        )
        
        if not exchange_rate_result.get("success", False):
            return {
                "error": f"Failed to fetch exchange rate: {exchange_rate_result.get('error', 'Unknown error')}",
                "hbar_amount": hbar_amount,
                "success": False
            }
        
        # Extract exchange rate data from Pydantic model
        data = exchange_rate_result.get("data")
        if not data:
            return {
                "error": "No exchange rate data available",
                "hbar_amount": hbar_amount,
                "success": False
            }
        
        # Access Pydantic model attributes directly
        current_rate = data.current_rate
        cent_equivalent = current_rate.cent_equivalent
        hbar_equivalent = current_rate.hbar_equivalent
        expiration_time = current_rate.expiration_time
        
        if hbar_equivalent == 0:
            return {
                "error": "Invalid exchange rate data: hbar_equivalent is zero",
                "hbar_amount": hbar_amount,
                "success": False
            }
        
        # Calculate USD values using integer arithmetic for precision
        # Convert hbar_amount to int if it's a string
        if isinstance(hbar_amount, str):
            tinybar_amount = int(hbar_amount)
        else:
            tinybar_amount = int(hbar_amount)
        
        # Convert tinybars to HBAR (1 HBAR = 100,000,000 tinybars)
        TINYBARS_PER_HBAR = 100000000
        hbar_amount_actual = tinybar_amount / TINYBARS_PER_HBAR
        
        # cent_equivalent is in cents, so divide by 100 to get dollars
        rate_usd_value = cent_equivalent / 100
        # Price per HBAR = (cent_equivalent / hbar_equivalent) / 100
        price_per_hbar = (cent_equivalent / hbar_equivalent) / 100
        # Total USD value = hbar_amount_actual * price_per_hbar
        total_usd_value = hbar_amount_actual * price_per_hbar
        
        return {
            "success": True,
            "tinybar_amount": tinybar_amount,
            "hbar_amount": round(hbar_amount_actual, 8),
            "usd_value": round(total_usd_value, 2),
            "price_per_hbar": round(price_per_hbar, 4),
            "exchange_rate_info": {
                "cent_equivalent": cent_equivalent,
                "hbar_equivalent": hbar_equivalent,
                "rate_usd_value": round(rate_usd_value, 2),
                "expiration_time": expiration_time
            },
            "calculation_timestamp": data.timestamp,
            "requested_timestamp": timestamp
        }
        
    except Exception as e:
        return {
            "error": f"Calculation failed: {str(e)}",
            "hbar_amount": hbar_amount,
            "success": False
        }

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


