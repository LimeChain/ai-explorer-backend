import os

from typing import Any, Dict, List, Union
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from .services.sdk_service import HederaSDKService
from .settings import settings
from .logging_config import setup_logging, get_logger, set_correlation_id
from .exceptions import (
    ServiceInitializationError, 
    DocumentProcessingError, 
    SDKError,
    ValidationError,
    handle_exception
)

from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__, service_name="mcp")

# Initialize the FastMCP server for Hedera Mirror Node
mcp = FastMCP("HederaMirrorNode")
network_sdk_service = {}
vector_store_service = None
document_processor = None

def get_sdk_service(network: str) -> HederaSDKService:
    global network_sdk_service
    if network not in network_sdk_service:
      try:
        network_sdk_service[network] = HederaSDKService(network=network)
        logger.info("✅ SDK service initialized successfully")
      except Exception as e:
            logger.error("❌ Failed to initialize SDK service", exc_info=True)
            raise ServiceInitializationError("HederaSDKService", str(e), e)
    return network_sdk_service[network]
    

def get_vector_services():
    """Initialize and return vector store services."""
    global vector_store_service, document_processor
    
    if vector_store_service is None or document_processor is None:
        # Initialize variables for exception handler
        vector_store_url = None
        collection_name = None
        embedding_model = None
        doc_path = None
        
        try:
            from .services.vector_store_service import VectorStoreService
            from .services.document_processor import DocumentProcessor
            
            # Get configuration from settings
            vector_store_url = settings.database_url
            llm_api_key = settings.llm_api_key.get_secret_value()
            collection_name = settings.collection_name
            embedding_model = settings.embedding_model
            doc_path = settings.sdk_documentation_path
            
            # Initialize services
            vector_store_service = VectorStoreService(
                connection_string=vector_store_url,
                llm_api_key=llm_api_key,
                collection_name=collection_name,
                embedding_model=embedding_model
            )
            
            document_processor = DocumentProcessor(vector_store_service)
            
            # Initialize with documentation file
            if os.path.exists(doc_path):
                document_processor.initialize_from_file(doc_path)
                logger.info("✅ Vector services initialized with documentation from %s", doc_path)
            else:
                raise FileNotFoundError(f"SDK documentation file not found: {doc_path}")
                
        except Exception as e:
            logger.error("❌ Failed to initialize vector services", exc_info=True, extra={
                "doc_path": doc_path,
                "vector_store_url": vector_store_url,
                "collection_name": collection_name,
                "embedding_model": embedding_model
            })
            raise ServiceInitializationError("VectorServices", str(e), e)
    
    return vector_store_service, document_processor

@mcp.tool()
async def call_sdk_method(method_name: str, network: str, **kwargs) -> Dict[str, Any]:
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

    # Set correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    # Input validation
    if not method_name or not isinstance(method_name, str):
        error_response = handle_exception(
            ValidationError("Method name is required and must be a string", "method_name", method_name),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Invalid method_name provided", extra={"method_name": method_name, "correlation_id": correlation_id})
        return error_response
    
    try:
        logger.info("🚀 Calling SDK method: %s", method_name, extra={
            "method_name": method_name,
            "parameters_count": len(kwargs),
            "correlation_id": correlation_id
        })
        
        result = await get_sdk_service(network).call_method(method_name, **kwargs)
        
        # Add correlation ID to successful results
        if isinstance(result, dict):
            result["correlation_id"] = correlation_id
        
        return result
        
    except SDKError as e:
        logger.error("❌ SDK error calling %s", method_name, exc_info=True, extra={
            "method_name": method_name,
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except Exception as e:
        logger.error("❌ Unexpected error calling %s", method_name, exc_info=True, extra={
            "method_name": method_name,
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})

@mcp.tool()
def retrieve_sdk_method(query: str) -> Dict[str, Any]:
    """
    Retrieve SDK methods using natural language queries via vector similarity search.
    
    This tool replaces get_available_methods and get_method_signature by using semantic
    search to find the most relevant SDK methods based on the user's natural language query.
    
    Args:
        query: Natural language description of what you want to do (e.g., "get account balance", "list transactions")
        
    Returns:
        Dict containing:
        - query: The original query
        - methods: List of matching methods with full details (name, description, parameters, returns, use_cases)
        - count: Number of methods returned
        
    Example usage:
        - retrieve_sdk_method(query="get account information")
        - retrieve_sdk_method(query="check token balance")
    """
    # Set correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    # Input validation
    if not query or not isinstance(query, str) or len(query.strip()) == 0:
        error_response = handle_exception(
            ValidationError("Query is required and must be a non-empty string", "query", query),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Invalid query provided", extra={"query": query, "correlation_id": correlation_id})
        return error_response
    
    try:
        logger.info("🔍 Retrieving SDK methods for query: %s", query, extra={
            "query": query,
            "correlation_id": correlation_id
        })
        
        # Get vector services
        _, document_processor = get_vector_services()

        # Search for methods
        search_result = document_processor.search_methods(query=query, k=3)
        
        result = {
            "query": query,
            "methods": search_result.get("methods", []),
            "success": True,
            "correlation_id": correlation_id
        }
        
        logger.info("✅ Retrieved %d methods for query", len(result['methods']), extra={
            "query": query,
            "methods_count": len(result['methods']),
            "correlation_id": correlation_id
        })
        
        return result

    except DocumentProcessingError as e:
        logger.error("❌ Document processing error during method retrieval", exc_info=True, extra={
            "query": query,
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except Exception as e:
        logger.error("❌ Unexpected error during method retrieval", exc_info=True, extra={
            "query": query,
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})

@mcp.tool()
async def calculate_hbar_value(hbar_amounts: Union[str, int, float, List[Union[str, int, float]]], network: str, timestamp: Union[str, int, float] = None) -> Dict[str, Any]:
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
    # Set correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    # Input validation (defensive check even though parameter is required)
    if hbar_amounts is None:
        error_response = handle_exception(
            ValidationError("hbar_amounts is required", "hbar_amounts", hbar_amounts),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Missing hbar_amounts parameter", extra={"correlation_id": correlation_id})
        return error_response
    
    # Validate hbar_amounts format
    if isinstance(hbar_amounts, list):
        if not hbar_amounts:
            error_response = handle_exception(
                ValidationError("hbar_amounts list cannot be empty", "hbar_amounts", hbar_amounts),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Empty hbar_amounts list provided", extra={"correlation_id": correlation_id})
            return error_response
        hbar_amount_list = hbar_amounts
    else:
        hbar_amount_list = [hbar_amounts]
    
    # Validate timestamp if provided
    if timestamp is not None:
        try:
            float(timestamp)
        except (ValueError, TypeError):
            error_response = handle_exception(
                ValidationError("timestamp must be a valid number", "timestamp", timestamp),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Invalid timestamp provided", extra={"timestamp": timestamp, "correlation_id": correlation_id})
            return error_response

    async def calculate_single_hbar_value(hbar_amount, timestamp, correlation_id):
        try:
            # Validate individual hbar_amount
            try:
                if isinstance(hbar_amount, str):
                    tinybar_amount = int(hbar_amount)
                else:
                    tinybar_amount = int(hbar_amount)
                
                if tinybar_amount < 0:
                    return {
                        "error": "HBAR amount cannot be negative",
                        "hbar_amount": hbar_amount,
                        "success": False,
                        "correlation_id": correlation_id
                    }
                    
            except (ValueError, TypeError):
                return {
                    "error": f"Invalid HBAR amount format: {hbar_amount}",
                    "hbar_amount": hbar_amount,
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            if not exchange_rate_result.get("success", False):
                return {
                    "error": f"Failed to fetch exchange rate: {exchange_rate_result.get('error', 'Unknown error')}",
                    "hbar_amount": hbar_amount,
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            # Extract exchange rate data from Pydantic model
            data = exchange_rate_result.get("data")
            if not data:
                return {
                    "error": "No exchange rate data available",
                    "hbar_amount": hbar_amount,
                    "success": False,
                    "correlation_id": correlation_id
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
                    "success": False,
                    "correlation_id": correlation_id
                }
            
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
                "requested_timestamp": timestamp,
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            logger.error("❌ Calculation failed for amount %s", hbar_amount, exc_info=True, extra={
                "hbar_amount": hbar_amount,
                "correlation_id": correlation_id
            })
            return {
                "error": f"Calculation failed: {str(e)}",
                "hbar_amount": hbar_amount,
                "success": False,
                "correlation_id": correlation_id
            }
    
    try:
        logger.info("💰 Calculating HBAR value for %d amount(s)", len(hbar_amount_list), extra={
            "amounts_count": len(hbar_amount_list),
            "has_timestamp": timestamp is not None,
            "correlation_id": correlation_id
        })
        
        calculations = {}
        all_successful = True
        exchange_rate_params = {}

        if timestamp:
            exchange_rate_params["timestamp"] = str(timestamp)

        # Fetch exchange rate using SDK service
        exchange_rate_result = await get_sdk_service(network).call_method(
            "get_network_exchange_rate", **exchange_rate_params
        )

        for hbar_amount in hbar_amount_list:
            result = await calculate_single_hbar_value(hbar_amount, timestamp, correlation_id)
            key = str(hbar_amount)
            calculations[key] = result
            if not result.get("success", False):
                all_successful = False

        final_result = {
            "calculations": calculations,
            "count": len(calculations),
            "success": all_successful,
            "correlation_id": correlation_id
        }
        
        logger.info("✅ HBAR value calculations completed", extra={
            "calculations_count": len(calculations),
            "all_successful": all_successful,
            "correlation_id": correlation_id
        })
        
        return final_result
        
    except SDKError as e:
        logger.error("❌ SDK error during HBAR value calculation", exc_info=True, extra={
            "amounts_count": len(hbar_amount_list),
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except Exception as e:
        logger.error("❌ Unexpected error during HBAR value calculation", exc_info=True, extra={
            "amounts_count": len(hbar_amount_list),
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})

@mcp.tool()
def convert_timestamp(timestamps: Union[str, int, float, List[Union[str, int, float]]]) -> Dict[str, Any]:
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
    # Set correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    # Input validation (defensive check even though parameter is required)
    if timestamps is None:
        error_response = handle_exception(
            ValidationError("timestamps is required", "timestamps", timestamps),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Missing timestamps parameter", extra={"correlation_id": correlation_id})
        return error_response
    
    # Validate timestamps format
    if isinstance(timestamps, list):
        if not timestamps:
            error_response = handle_exception(
                ValidationError("timestamps list cannot be empty", "timestamps", timestamps),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Empty timestamps list provided", extra={"correlation_id": correlation_id})
            return error_response
        timestamp_list = timestamps
    else:
        timestamp_list = [timestamps]

    def convert_single_timestamp(timestamp, correlation_id):
        try:
            timestamp_str = str(timestamp)
            
            # Basic validation of timestamp string
            if not timestamp_str or timestamp_str.strip() == "":
                return {
                    "original_timestamp": timestamp,
                    "error": "Timestamp cannot be empty",
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            if '.' in timestamp_str:
                # Hedera format with seconds.nanoseconds
                parts = timestamp_str.split('.')
                if len(parts) != 2:
                    return {
                        "original_timestamp": timestamp,
                        "error": "Invalid timestamp format: multiple decimal points",
                        "success": False,
                        "correlation_id": correlation_id
                    }
                
                seconds_str = parts[0]
                nanoseconds_str = parts[1]
                
                try:
                    unix_seconds = int(seconds_str)
                    nanoseconds = int(nanoseconds_str.ljust(9, '0')[:9])  # Pad/truncate to 9 digits
                except ValueError:
                    return {
                        "original_timestamp": timestamp,
                        "error": "Invalid timestamp format: non-numeric components",
                        "success": False,
                        "correlation_id": correlation_id
                    }
            else:
                # Unix timestamp
                try:
                    unix_seconds = int(float(timestamp_str))
                    nanoseconds = 0
                except ValueError:
                    return {
                        "original_timestamp": timestamp,
                        "error": "Invalid timestamp format: not a valid number",
                        "success": False,
                        "correlation_id": correlation_id
                    }
            
            # Validate timestamp range (reasonable bounds)
            if unix_seconds < 0:
                return {
                    "original_timestamp": timestamp,
                    "error": "Timestamp cannot be negative",
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            if unix_seconds > 4102444800:  # Year 2100
                return {
                    "original_timestamp": timestamp,
                    "error": "Timestamp too far in the future (beyond year 2100)",
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            dt = datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
            
            human_readable = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            iso_format = dt.isoformat()
            
            return {
                "original_timestamp": timestamp,
                "unix_seconds": unix_seconds,
                "nanoseconds": nanoseconds,
                "human_readable": human_readable,
                "iso_format": iso_format,
                "success": True,
                "correlation_id": correlation_id
            }
            
        except (ValueError, OverflowError) as e:
            logger.warning("⚠️ Timestamp conversion failed for %s", timestamp, extra={
                "timestamp": timestamp,
                "error": str(e),
                "correlation_id": correlation_id
            })
            return {
                "original_timestamp": timestamp,
                "error": f"Invalid timestamp format: {str(e)}",
                "success": False,
                "correlation_id": correlation_id
            }
        except Exception as e:
            logger.error("❌ Unexpected error converting timestamp %s", timestamp, exc_info=True, extra={
                "timestamp": timestamp,
                "correlation_id": correlation_id
            })
            return {
                "original_timestamp": timestamp,
                "error": f"Conversion failed: {str(e)}",
                "success": False,
                "correlation_id": correlation_id
            }
    
    try:
        logger.info("🔄 Converting %d timestamp(s)", len(timestamp_list), extra={
            "timestamps_count": len(timestamp_list),
            "correlation_id": correlation_id
        })
        
        conversions = {}
        all_successful = True
        
        for timestamp in timestamp_list:
            result = convert_single_timestamp(timestamp, correlation_id)
            key = str(timestamp)
            conversions[key] = result
            if not result.get("success", False):
                all_successful = False

        final_result = {
            "conversions": conversions,
            "count": len(conversions),
            "success": all_successful,
            "correlation_id": correlation_id
        }
        
        logger.info("✅ Timestamp conversions completed", extra={
            "conversions_count": len(conversions),
            "all_successful": all_successful,
            "correlation_id": correlation_id
        })
        
        return final_result
        
    except Exception as e:
        logger.error("❌ Unexpected error during timestamp conversion", exc_info=True, extra={
            "timestamps_count": len(timestamp_list),
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})


