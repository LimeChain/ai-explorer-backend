import os

from typing import Any, Dict, List, Union
from datetime import datetime, timezone

from hiero_mirror.async_client import AsyncMirrorNodeClient
from hiero_mirror.client import MirrorNodeClient
from mcp.server.fastmcp import FastMCP

from .services.sdk_service import HederaSDKService
from .services.saucerswap_service import SaucerSwapService
from .services.graphql_service import GraphQLService
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
ASYNC_METHODS = ["get_transactions", "get_account", "get_token_balances"]
network_sdk_service = {}
async_network_sdk_service = {}
vector_store_service = None
document_processor = None
graphql_service = None

def get_sdk_service(network: str) -> HederaSDKService:
    global network_sdk_service
    if network not in network_sdk_service:
      try:
        network_sdk_service[network] = HederaSDKService(client=MirrorNodeClient.for_network(network))
        logger.info("✅ SDK service initialized successfully")
      except Exception as e:
            logger.error("❌ Failed to initialize SDK service", exc_info=True)
            raise ServiceInitializationError("HederaSDKService", str(e), e)
    return network_sdk_service[network]

def get_async_sdk_service(network: str) -> HederaSDKService:
    global async_network_sdk_service
    if network not in async_network_sdk_service:
      try:
        async_network_sdk_service[network] = HederaSDKService(client=AsyncMirrorNodeClient.for_network(network, request_timeout=settings.request_timeout))
        logger.info("✅ Async SDK service initialized successfully")
      except Exception as e:
            logger.error("❌ Failed to initialize async SDK service", exc_info=True)
            raise ServiceInitializationError("HederaSDKService", str(e), e)
    return async_network_sdk_service[network]
    

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

def get_graphql_service() -> GraphQLService:
    """Initialize and return GraphQL service."""
    global graphql_service
    
    if graphql_service is None:
        try:
            # Get configuration from settings
            hgraph_endpoint = settings.hgraph_endpoint
            hgraph_api_key = settings.hgraph_api_key
            llm_api_key = settings.llm_api_key.get_secret_value()
            llm_model = settings.llm_model
            llm_provider = settings.llm_provider
            embedding_model = settings.embedding_model
            connection_string = settings.database_url
            schema_path = settings.graphql_schema_path
            
            # Initialize GraphQL service
            graphql_service = GraphQLService(
                hgraph_endpoint=hgraph_endpoint,
                hgraph_api_key=hgraph_api_key,
                llm_api_key=llm_api_key,
                connection_string=connection_string,
                llm_model=llm_model,
                llm_provider=llm_provider,
                embedding_model=embedding_model,
                schema_path=schema_path
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GraphQL service: {e}") from e
    
    return graphql_service

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
        if (method_name in ASYNC_METHODS):
            result = await get_async_sdk_service(network).call_method(method_name, **kwargs)
        else:
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


# Helper functions for HBAR value calculations

def normalize_hbar_amounts(hbar_amounts: Union[str, int, float, List[Union[str, int, float]]]) -> List[Union[str, int, float]]:
    """
    Normalize input to always return a list of amounts.
    
    Args:
        hbar_amounts: Single amount or list of amounts
        
    Returns:
        List of amounts
        
    Raises:
        ValidationError: If input is invalid
    """
    if hbar_amounts is None:
        raise ValidationError("hbar_amounts is required", "hbar_amounts", hbar_amounts)
    
    if isinstance(hbar_amounts, list):
        if not hbar_amounts:
            raise ValidationError("hbar_amounts list cannot be empty", "hbar_amounts", hbar_amounts)
        return hbar_amounts
    else:
        return [hbar_amounts]


def validate_hbar_amount(hbar_amount: Union[str, int, float]) -> int:
    """
    Validate and convert a single HBAR amount to tinybars.
    
    Args:
        hbar_amount: Amount in tinybars (string, int, or float)
        
    Returns:
        Validated amount as integer (tinybars)
        
    Raises:
        ValidationError: If amount is invalid
    """
    try:
        if isinstance(hbar_amount, float):
            raise ValidationError("HBAR amount must be an integer of tinybars; floats are not supported", "hbar_amount", hbar_amount)
        if isinstance(hbar_amount, str):
            tinybar_amount = int(hbar_amount)
        else:
            tinybar_amount = int(hbar_amount)
        
        if tinybar_amount < 0:
            raise ValidationError("HBAR amount cannot be negative", "hbar_amount", hbar_amount)
            
        return tinybar_amount
        
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid HBAR amount format: {hbar_amount}", "hbar_amount", hbar_amount) from e


def build_error_response(error_msg: str, hbar_amount: Union[str, int, float], correlation_id: str) -> Dict[str, Any]:
    """
    Build a standardized error response for a single calculation.
    
    Args:
        error_msg: Error message
        hbar_amount: Original amount that failed
        correlation_id: Request correlation ID
        
    Returns:
        Standardized error response dictionary
    """
    return {
        "error": error_msg,
        "hbar_amount": hbar_amount,
        "success": False,
        "correlation_id": correlation_id
    }


def build_success_response(
    tinybar_amount: int, 
    hbar_amount_actual: float, 
    price_per_hbar: float, 
    price_data: Dict[str, Any], 
    correlation_id: str
) -> Dict[str, Any]:
    """
    Build a standardized success response for a single calculation.
    
    Args:
        tinybar_amount: Amount in tinybars (integer)
        hbar_amount_actual: Amount in HBAR (float)
        price_per_hbar: Current HBAR price in USD
        price_data: Price data from SaucerSwap
        correlation_id: Request correlation ID
        
    Returns:
        Standardized success response dictionary
    """
    from decimal import Decimal, ROUND_HALF_UP
    hbar_dec = (Decimal(tinybar_amount) / Decimal(100_000_000))
    usd_dec = (hbar_dec * Decimal(str(price_per_hbar))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return {
        "success": True,
        "tinybar_amount": tinybar_amount,
        "hbar_amount": float(hbar_dec.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)),
        "usd_value": float(usd_dec),
        "price_per_hbar": float(Decimal(str(price_per_hbar)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)),
        "calculation_timestamp": price_data.get("timestamp"),
        "correlation_id": correlation_id
    }


async def calculate_single_hbar_value(
    hbar_amount: Union[str, int, float], 
    price_data: Dict[str, Any], 
    correlation_id: str
) -> Dict[str, Any]:
    """
    Calculate USD value for a single HBAR amount.
    
    Args:
        hbar_amount: Amount in tinybars
        price_data: Price data from SaucerSwap API
        correlation_id: Request correlation ID
        
    Returns:
        Calculation result dictionary with success/error info
    """
    try:
        # Validate the amount
        tinybar_amount = validate_hbar_amount(hbar_amount)
        
        # Check if price data is valid
        if not price_data.get("success", False):
            return build_error_response(
                f"Failed to fetch HBAR price: {price_data.get('error', 'Unknown error')}",
                hbar_amount,
                correlation_id
            )
        
        # Extract price from SaucerSwap response
        price_per_hbar = price_data.get("price_usd", 0)
        if price_per_hbar <= 0:
            return build_error_response(
                "Invalid price data: price_usd is zero or negative",
                hbar_amount,
                correlation_id
            )
        
        # Convert tinybars to HBAR (1 HBAR = 100,000,000 tinybars)
        TINYBARS_PER_HBAR = 100000000
        hbar_amount_actual = tinybar_amount / TINYBARS_PER_HBAR
        
        # Build success response
        return build_success_response(
            tinybar_amount, 
            hbar_amount_actual, 
            price_per_hbar, 
            price_data, 
            correlation_id
        )
        
    except ValidationError as e:
        return build_error_response(str(e), hbar_amount, correlation_id)
        
    except Exception as e:
        logger.error("❌ Calculation failed for amount %s", hbar_amount, exc_info=True, extra={
            "hbar_amount": hbar_amount,
            "correlation_id": correlation_id
        })
        return build_error_response(f"Calculation failed: {str(e)}", hbar_amount, correlation_id)


@mcp.tool()
async def calculate_hbar_value(hbar_amounts: Union[str, int, float, List[Union[str, int, float]]], network: str, timestamp: Union[str, int, float] = None) -> Dict[str, Any]:
    """
    Calculate the USD value of HBAR tokens using real-time SaucerSwap pricing.
    
    This tool fetches the current HBAR price from SaucerSwap API and calculates the equivalent
    USD value for the specified amount(s) in tinybars. 1 HBAR = 100,000,000 tinybars.
    Accepts single amount or list of amounts. Provides more up-to-date pricing than network exchange rates.
    
    Args:
        hbar_amounts: Single amount or list of amounts in tinybars to calculate USD values for (supports large integers)
        network: Network parameter (maintained for compatibility, not used with SaucerSwap)
        timestamp: Optional Unix timestamp (ignored - SaucerSwap provides real-time data only)
        
    Returns:
        Dict with "calculations" key mapping original amounts to calculation details,
        "count" with number of amounts processed, and "success" indicating if all calculations succeeded
        
    Example usage:
        - calculate_hbar_value(hbar_amounts=150000000000) -> {"calculations": {"150000000000": {...}}, "count": 1, "success": True}
        - calculate_hbar_value(hbar_amounts=["1000000000000", 3000000000000]) -> {"calculations": {"1000000000000": {...}, "3000000000000": {...}}, "count": 2, "success": True}
        - calculate_hbar_value(hbar_amounts=3000000000000, timestamp=1705276800) -> timestamp ignored, uses current SaucerSwap price
    """
    # Setup correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    try:
        # 1. Normalize inputs (single amount -> list)
        hbar_amount_list = normalize_hbar_amounts(hbar_amounts)
        
        logger.info("💰 Calculating HBAR value for %d amount(s)", len(hbar_amount_list), extra={
            "amounts_count": len(hbar_amount_list),
            "correlation_id": correlation_id
        })
        
        # 2. Fetch current HBAR price from SaucerSwap (once for all calculations)
        async with SaucerSwapService() as saucerswap:
            hbar_price_result = await saucerswap.get_hbar_price(correlation_id)
        
        # 3. Calculate values for all amounts
        calculations = {}
        all_successful = True
        
        for hbar_amount in hbar_amount_list:
            result = await calculate_single_hbar_value(hbar_amount, hbar_price_result, correlation_id)
            calculations[str(hbar_amount)] = result
            if not result.get("success", False):
                all_successful = False
        
        # 4. Build and return response
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
        
    except ValidationError as e:
        logger.warning("⚠️ Validation error in calculate_hbar_value", extra={
            "error": str(e),
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except SDKError as e:
        logger.error("❌ SaucerSwap API error during HBAR value calculation", exc_info=True, extra={
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except Exception as e:
        logger.error("❌ Unexpected error during HBAR value calculation", exc_info=True, extra={
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})

@mcp.tool()
async def process_tokens_with_balances(token_data: List[Dict[str, Any]], network: str) -> Dict[str, Any]:
    """
    Process a list of tokens with their balances, fetch token details, and convert amounts using proper decimals.
    
    This tool takes token data with raw balances (in tinybars) and fetches the corresponding token 
    details to perform proper decimal conversion. It eliminates the need for multiple get_token calls
    and prevents decimal conversion errors in the agent.
    
    Args:
        token_data: List of token data with format [{"token_id": "0.0.456858", "balance": 353156}]
        network: Network to use for API calls
        
    Returns:
        Dict containing:
        - tokens: List of processed token data with converted balances
        - count: Number of tokens processed
        - success: Whether all processing succeeded
        
    Example usage:
        - process_tokens_with_balances([{"token_id": "0.0.456858", "balance": 353156}], "mainnet")
    """
    # Set correlation ID for request tracking
    correlation_id = set_correlation_id()
    
    # Input validation
    if not token_data or not isinstance(token_data, list):
        error_response = handle_exception(
            ValidationError("token_data is required and must be a non-empty list", "token_data", token_data),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Invalid token_data provided", extra={"token_data": token_data, "correlation_id": correlation_id})
        return error_response
    # Validate token data structure
    for idx, item in enumerate(token_data):
        if not isinstance(item, dict):
            error_response = handle_exception(
                ValidationError(f"token_data[{idx}] must be a dictionary", "token_data", item),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Invalid token data structure", extra={"item": item, "index": idx, "correlation_id": correlation_id})
            return error_response
        
        if "token_id" not in item:
            error_response = handle_exception(
                ValidationError(f"token_data[{idx}] missing required field 'token_id'", "token_data", item),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Missing token_id", extra={"item": item, "index": idx, "correlation_id": correlation_id})
            return error_response
        
        if "balance" not in item:
            error_response = handle_exception(
                ValidationError(f"token_data[{idx}] missing required field 'balance'", "token_data", item),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ Missing balance", extra={"item": item, "index": idx, "correlation_id": correlation_id})
            return error_response

    
    if not network or not isinstance(network, str):
        error_response = handle_exception(
            ValidationError("network is required and must be a string", "network", network),
            {"correlation_id": correlation_id}
        )
        logger.warning("⚠️ Invalid network provided", extra={"network": network, "correlation_id": correlation_id})
        return error_response

    async def process_single_token(token_info, balance, correlation_id):
        try:
            # Validate balance
            try:
                raw_balance = int(balance)
                if raw_balance < 0:
                    return {
                        "error": "Token balance cannot be negative",
                        "token_id": token_info.get("token_id", "unknown"),
                        "success": False,
                        "correlation_id": correlation_id
                    }
            except (ValueError, TypeError):
                return {
                    "error": f"Invalid balance format: {balance}",
                    "token_id": token_info.get("token_id", "unknown"),
                    "success": False,
                    "correlation_id": correlation_id
                }
            
            # Extract token details from the fetched token info
            token_id = token_info.get("token_id", "")
            name = token_info.get("name", "Unknown Token")
            symbol = token_info.get("symbol", "")
            decimals = token_info.get("decimals", 0)
            
            # Convert balance using decimals
            if decimals > 0:
                converted_balance = raw_balance / (10 ** decimals)
            else:
                converted_balance = raw_balance
            
            # Format the balance for display
            if decimals > 0:
                # Format to reasonable precision, removing trailing zeros
                formatted_balance = f"{converted_balance:.{decimals}f}".rstrip('0').rstrip('.')
            else:
                formatted_balance = str(raw_balance)
            
            # Include symbol in formatted display if available
            display_balance = f"{formatted_balance} {symbol}".strip() if symbol else formatted_balance
            
            return {
                "token_id": token_id,
                "name": name,
                "symbol": symbol,
                "decimals": decimals,
                "raw_balance": raw_balance,
                "converted_balance": str(converted_balance),
                "formatted_balance": display_balance,
                "success": True,
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            logger.error("❌ Processing failed for token %s", token_info.get("token_id", "unknown"), exc_info=True, extra={
                "token_id": token_info.get("token_id", "unknown"),
                "balance": balance,
                "correlation_id": correlation_id
            })
            return {
                "error": f"Processing failed: {str(e)}",
                "token_id": token_info.get("token_id", "unknown"),
                "success": False,
                "correlation_id": correlation_id
            }

    try:
        logger.info("🪙 Processing %d token(s) with balances", len(token_data), extra={
            "tokens_count": len(token_data),
            "correlation_id": correlation_id
        })
        
        # Extract unique token IDs for batch fetching
        token_ids = []
        balance_map = {}
        
        for item in token_data:
            if not isinstance(item, dict) or "token_id" not in item or "balance" not in item:
                logger.warning("⚠️ Invalid token data item skipped", extra={
                    "item": item,
                    "correlation_id": correlation_id
                })
                continue
            
            token_id = item["token_id"]
            balance = item["balance"]
            
            if token_id not in balance_map:
                token_ids.append(token_id)
            balance_map[token_id] = balance
        
        if not token_ids:
            error_response = handle_exception(
                ValidationError("No valid token data found", "token_data", token_data),
                {"correlation_id": correlation_id}
            )
            logger.warning("⚠️ No valid token IDs found", extra={"correlation_id": correlation_id})
            return error_response
        
        # Batch fetch token details using get_tokens with multiple calls if needed
        # Since get_tokens doesn't support multiple token_ids in one call, we'll call get_token for each
        # But we can optimize this by calling them concurrently
        token_details = {}
        
        for token_id in token_ids:
            try:
                result = await get_sdk_service(network).call_method("get_token", token_id=token_id)
                if result.get("success", False) and "data" in result:
                    # Extract token info from the SDK response
                    token_info = result["data"]
                    token_details[token_id] = {
                        "token_id": token_id,
                        "name": getattr(token_info, "name", "Unknown Token"),
                        "symbol": getattr(token_info, "symbol", ""),
                        "decimals": int(getattr(token_info, "decimals", 0))
                    }
                else:
                    logger.warning("⚠️ Failed to fetch token details for %s", token_id, extra={
                        "token_id": token_id,
                        "result": result,
                        "correlation_id": correlation_id
                    })
                    token_details[token_id] = {
                        "token_id": token_id,
                        "name": "Unknown Token",
                        "symbol": "",
                        "decimals": 0,
                        "error": result.get("error", "Failed to fetch token details")
                    }
            except Exception as e:
                logger.error("❌ Error fetching token details for %s", token_id, exc_info=True, extra={
                    "token_id": token_id,
                    "correlation_id": correlation_id
                })
                token_details[token_id] = {
                    "token_id": token_id,
                    "name": "Unknown Token", 
                    "symbol": "",
                    "decimals": 0,
                    "error": f"Fetch failed: {str(e)}"
                }
        
        # Process each token with its balance
        processed_tokens = []
        all_successful = True
        
        for token_id in token_ids:
            token_info = token_details[token_id]
            balance = balance_map[token_id]
            
            result = await process_single_token(token_info, balance, correlation_id)
            processed_tokens.append(result)
            
            if not result.get("success", False):
                all_successful = False

        final_result = {
            "tokens": processed_tokens,
            "count": len(processed_tokens),
            "success": all_successful,
            "correlation_id": correlation_id
        }
        
        logger.info("✅ Token processing completed", extra={
            "tokens_count": len(processed_tokens),
            "all_successful": all_successful,
            "correlation_id": correlation_id
        })
        
        return final_result
        
    except SDKError as e:
        logger.error("❌ SDK error during token processing", exc_info=True, extra={
            "tokens_count": len(token_data),
            "correlation_id": correlation_id
        })
        return handle_exception(e, {"correlation_id": correlation_id})
    
    except Exception as e:
        logger.error("❌ Unexpected error during token processing", exc_info=True, extra={
            "tokens_count": len(token_data),
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

@mcp.tool()
async def text_to_graphql_query(question: str) -> Dict[str, Any]:
    """
    Execute natural language queries against Hedera data using GraphQL through Hgraph API.
    
    This tool translates natural language questions into GraphQL queries and executes them
    against the Hgraph API, which provides access to current Hedera network state and data.
    It should be used for questions about current network state, live data, and real-time queries.
    
    The tool will:
    1. Generate appropriate GraphQL based on the Hedera schema from Hgraph
    2. Execute the query against the Hgraph API
    3. Return formatted results
    
    Args:
        question: Natural language question about Hedera network data
        
    Returns:
        Dict containing:
        - success: Whether the query was successful
        - question: The original question
        - graphql_query: The generated GraphQL query
        - data: Query results as nested dictionaries
        - response_size: Size of the response data
        - error: Error message if something went wrong
        
    Example usage:
        - text_to_graphql_query(question="What are the latest transactions for account 0.0.123?")
        - text_to_graphql_query(question="Show me token information for token ID 0.0.456789")
        - text_to_graphql_query(question="Get account balance for 0.0.98?")
    """
    try:
        logger.info(f"🔍 TEXT-TO-GRAPHQL TOOL: Starting with question: '{question[:100]}{'...' if len(question) > 100 else ''}'")
        
        # Get GraphQL service
        logger.info("🔧 TEXT-TO-GRAPHQL TOOL: Initializing GraphQL service")
        gql_service = get_graphql_service()
        logger.info("✅ TEXT-TO-GRAPHQL TOOL: GraphQL service initialized successfully")
        
        # Execute text-to-GraphQL pipeline
        logger.info("🚀 TEXT-TO-GRAPHQL TOOL: Starting text-to-GraphQL pipeline")
        result = await gql_service.text_to_graphql_query(question)
        
        # Log the results
        success = result.get("success", False)
        graphql_query = result.get("graphql_query", "")
        data_size = len(str(result.get("data", {})))
        response_size = result.get("response_size", 0)
        total_attempts = result.get("total_attempts", 0)
        
        if success:
            logger.info(f"✅ TEXT-TO-GRAPHQL TOOL: Pipeline completed successfully")
            logger.info(f"📊 TEXT-TO-GRAPHQL TOOL: Response data size: {data_size} chars, Response size: {response_size}")
            if total_attempts > 1:
                logger.info(f"🔄 TEXT-TO-GRAPHQL TOOL: Required {total_attempts} attempts")
            
            # Log the actual GraphQL query that was executed
            if graphql_query:
                logger.info(f"📝 TEXT-TO-GRAPHQL TOOL: Generated GraphQL query:")
                # Log each line of the query for better readability
                for i, line in enumerate(graphql_query.strip().split('\n'), 1):
                    logger.info(f"    {i:2d}: {line}")
            
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ TEXT-TO-GRAPHQL TOOL: Pipeline failed: {error_msg}")
            if total_attempts > 0:
                logger.error(f"🔄 TEXT-TO-GRAPHQL TOOL: Failed after {total_attempts} attempts")
            
            # Still log the query if it was generated (for debugging)
            if graphql_query:
                logger.error(f"📝 TEXT-TO-GRAPHQL TOOL: Failed GraphQL query:")
                for i, line in enumerate(graphql_query.strip().split('\n'), 1):
                    logger.error(f"    {i:2d}: {line}")
        
        return {
            "success": success,
            "question": question,
            "graphql_query": graphql_query,
            "data": result.get("data", {}),
            "response_size": response_size,
            "error": result.get("error", ""),
            "total_attempts": total_attempts
        }
        
    except Exception as e:
        logger.error(f"💥 TEXT-TO-GRAPHQL TOOL: Tool execution failed with exception: {str(e)}", exc_info=True)
        return {
            "success": False,
            "question": question,
            "error": f"Text-to-GraphQL tool failed: {str(e)}",
        }


