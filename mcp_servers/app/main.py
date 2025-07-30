import os

from typing import Any, Dict, List, Union
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from .services.sdk_service import HederaSDKService

from dotenv import load_dotenv

load_dotenv()

# Initialize the FastMCP server for Hedera Mirror Node
mcp = FastMCP("HederaMirrorNode")
sdk_service = None
vector_store_service = None
document_processor = None

def get_sdk_service() -> HederaSDKService:
    global sdk_service
    if sdk_service is None:
        sdk_service = HederaSDKService()
    return sdk_service

def get_vector_services():
    """Initialize and return vector store services."""
    global vector_store_service, document_processor
    
    if vector_store_service is None or document_processor is None:
        try:
            from .services.vector_store_service import VectorStoreService
            from .services.document_processor import DocumentProcessor
            
            # Get configuration from environment variables
            vector_store_url = os.getenv("VECTOR_STORE_URL") # TODO: look for a way to utilize settings module
            openai_api_key = os.getenv("OPENAI_API_KEY") # TODO: look for a way to utilize settings module
            collection_name = os.getenv("COLLECTION_NAME") # TODO: look for a way to utilize settings module
            embedding_model = os.getenv("EMBEDDING_MODEL") # TODO: look for a way to utilize settings module
            
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            
            # Initialize services
            vector_store_service = VectorStoreService(
                connection_string=vector_store_url,
                openai_api_key=openai_api_key,
                collection_name=collection_name,
                embedding_model=embedding_model
            )
            
            document_processor = DocumentProcessor(vector_store_service)
            
            # Initialize with documentation file
            doc_path = "hiero_mirror_sdk_methods_documentation.json" # TODO: make this dynamic
            if os.path.exists(doc_path):
                document_processor.initialize_from_file(doc_path)
            else:
                raise FileNotFoundError(f"SDK documentation file not found: {doc_path}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to initialize vector services: {e}")
    
    return vector_store_service, document_processor

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
async def retrieve_sdk_method(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Retrieve SDK methods using natural language queries via vector similarity search.
    
    This tool replaces get_available_methods and get_method_signature by using semantic
    search to find the most relevant SDK methods based on the user's natural language query.
    
    Args:
        query: Natural language description of what you want to do (e.g., "get account balance", "list transactions")
        max_results: Maximum number of methods to return (default: 3, max: 10)
        
    Returns:
        Dict containing:
        - query: The original query
        - methods: List of matching methods with full details (name, description, parameters, returns, use_cases)
        - count: Number of methods returned
        
    Example usage:
        - retrieve_sdk_method(query="get account information")
        - retrieve_sdk_method(query="list recent transactions", max_results=5)
        - retrieve_sdk_method(query="check token balance")
    """
    try:
        # Limit max_results to prevent excessive API calls
        max_results = min(max(1, max_results), 10)
        # Get vector services
        _, document_processor = get_vector_services()
        
        # Search for methods
        search_result = document_processor.search_methods(query=query, k=max_results)
        
        return {
            "query": query,
            "methods": search_result.get("methods", []),
            "success": True
        }
        
    except Exception as e:
        return {
            "query": query,
            "methods": [],
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def calculate_hbar_value(hbar_amounts: Union[str, int, float, List[Union[str, int, float]]], timestamp: Union[str, int, float] = None) -> Dict[str, Any]:
    """
    Calculate the USD value of HBAR tokens using current exchange rates.
    
    This tool fetches the current HBAR exchange rate and calculates the equivalent
    USD value for the specified amount(s) in tinybars. 1 HBAR = 100,000,000 tinybars.
    Accepts single amount or list of amounts.
    
    Args:
        hbar_amounts: Single amount or list of amounts in tinybars to calculate USD values for (supports large integers)
        timestamp: Optional Unix timestamp (epoch) to get historical exchange rates
        
    Returns:
        Dict with "calculations" key mapping original amounts to calculation details,
        "count" with number of amounts processed, and "success" indicating if all calculations succeeded
        
    Example usage:
        - calculate_hbar_value(hbar_amounts=150000000000) -> {"calculations": {"150000000000": {...}}, "count": 1, "success": True}
        - calculate_hbar_value(hbar_amounts=["1000000000000", 3000000000000]) -> {"calculations": {"1000000000000": {...}, "3000000000000": {...}}, "count": 2, "success": True}
        - calculate_hbar_value(hbar_amounts=3000000000000, timestamp=1705276800) -> historical calculation for epoch timestamp
    """
    async def calculate_single_hbar_value(hbar_amount, timestamp):
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
    
    if isinstance(hbar_amounts, list):
        hbar_amount_list = hbar_amounts
    else:
        hbar_amount_list = [hbar_amounts]
    
    calculations = {}
    all_successful = True
    
    for hbar_amount in hbar_amount_list:
        result = await calculate_single_hbar_value(hbar_amount, timestamp)
        key = str(hbar_amount)
        calculations[key] = result
        if not result.get("success", False):
            all_successful = False
    
    return {
        "calculations": calculations,
        "count": len(calculations),
        "success": all_successful
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
async def convert_timestamp(timestamps: Union[str, int, float, List[Union[str, int, float]]]) -> Dict[str, Any]:
    """
    Convert Unix timestamp(s) to human-readable date format.
    
    Handles both regular Unix timestamps (seconds since epoch) and Hedera timestamps 
    with nanosecond precision (seconds.nanoseconds format). Accepts single timestamp
    or list of timestamps.
    
    Args:
        timestamps: Single timestamp or list of timestamps (int, float, string)
        
    Returns:
        Dict with "conversions" key mapping original timestamps to conversion details,
        "count" with number of timestamps processed, and "success" indicating if all conversions succeeded
        
    Example usage:
        - convert_timestamp(1752127198.022577) -> {"conversions": {"1752127198.022577": {...}}, "count": 1, "success": True}
        - convert_timestamp([1752127198, "1752127200.123456"]) -> {"conversions": {"1752127198": {...}, "1752127200.123456": {...}}, "count": 2, "success": True}
    """
    def convert_single_timestamp(timestamp):
        try:
            timestamp_str = str(timestamp)
            
            if '.' in timestamp_str:
                # Hedera format with seconds.nanoseconds
                seconds_str = timestamp_str.split('.')[0]
                nanoseconds_str = timestamp_str.split('.')[1]
                unix_seconds = int(seconds_str)
                nanoseconds = int(nanoseconds_str.ljust(9, '0')[:9])  # Pad/truncate to 9 digits
            else:
                # Unix timestamp
                unix_seconds = int(float(timestamp_str))
                nanoseconds = 0
            
            dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
            
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
    
    if isinstance(timestamps, list):
        timestamp_list = timestamps
    else:
        timestamp_list = [timestamps]
    
    conversions = {}
    all_successful = True
    
    for timestamp in timestamp_list:
        result = convert_single_timestamp(timestamp)
        key = str(timestamp)
        conversions[key] = result
        if not result.get("success", False):
            all_successful = False
    
    return {
        "conversions": conversions,
        "count": len(conversions),
        "success": all_successful
    }


