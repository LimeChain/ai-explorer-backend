"""
SaucerSwap API service for real-time token pricing.
"""
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from ..settings import settings
from ..logging_config import get_logger
from ..exceptions import ServiceInitializationError, SDKError

logger = get_logger(__name__)


class SaucerSwapService:
    """
    Service for interacting with SaucerSwap API to get real-time token prices.
    
    Provides methods to fetch current USD prices for tokens on the Hedera network
    using SaucerSwap's REST API.
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize SaucerSwap service.
        
        Args:
            base_url: Base URL for SaucerSwap API (defaults to settings value)
            api_key: API key for SaucerSwap (defaults to settings value)
        """
        self.base_url = base_url or settings.saucerswap_base_url
        self.api_key = api_key or settings.saucerswap_api_key.get_secret_value()
        
        if not self.api_key:
            raise ServiceInitializationError(
                "SaucerSwapService", 
                "SaucerSwap API key is required",
                ValueError("Missing saucerswap_api_key")
            )
        
        # Initialize HTTP client with default headers
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "AI-Explorer-Backend/1.0"
            },
            timeout=httpx.Timeout(settings.request_timeout)
        )
        
        logger.info("✅ SaucerSwap service initialized", extra={
            "base_url": self.base_url
        })
    
    async def get_token_price(self, token_id: str, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current USD price for a token from SaucerSwap API.
        
        Args:
            token_id: Hedera token ID (e.g., "0.0.1456986" for HBAR)
            correlation_id: Optional correlation ID for request tracking
            
        Returns:
            Dict containing:
            - success: Boolean indicating if the request was successful
            - price_usd: Float USD price per token
            - timestamp: ISO timestamp of when the price was fetched
            - correlation_id: Request correlation ID
            
        Raises:
            SDKError: If the API request fails or returns invalid data
        """
        try:
            logger.info("🔍 Fetching token price from SaucerSwap", extra={
                "token_id": token_id,
                "correlation_id": correlation_id
            })
            
            # Make API request
            response = await self.client.get(f"/tokens/{token_id}")
            response.raise_for_status()
            
            data = response.json()
            
            # Validate response structure
            if "priceUsd" not in data:
                raise SDKError(
                    "Invalid SaucerSwap response: missing priceUsd field",
                    {"token_id": token_id, "response_keys": list(data.keys())}
                )
            
            # Extract price and convert to float
            price_usd = float(data["priceUsd"])
            
            result = {
                "success": True,
                "price_usd": price_usd,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id
            }
            
            logger.info("✅ Successfully fetched token price", extra={
                "token_id": token_id,
                "price_usd": price_usd,
                "token_symbol": data.get("symbol"),
                "correlation_id": correlation_id
            })
            
            return result
            
        except httpx.HTTPStatusError as e:
            error_msg = f"SaucerSwap API HTTP error: {e.response.status_code}"
            logger.error("❌ SaucerSwap API HTTP error", extra={
                "token_id": token_id,
                "status_code": e.response.status_code,
                "response_text": e.response.text[:500],
                "correlation_id": correlation_id
            })
            raise SDKError(error_msg, {
                "token_id": token_id,
                "status_code": e.response.status_code,
                "correlation_id": correlation_id
            })
            
        except httpx.RequestError as e:
            error_msg = f"SaucerSwap API request error: {str(e)}"
            logger.error("❌ SaucerSwap API request error", exc_info=True, extra={
                "token_id": token_id,
                "correlation_id": correlation_id
            })
            raise SDKError(error_msg, {
                "token_id": token_id,
                "error_type": type(e).__name__,
                "correlation_id": correlation_id
            })
            
        except (ValueError, KeyError) as e:
            error_msg = f"Invalid SaucerSwap API response: {str(e)}"
            logger.error("❌ Invalid SaucerSwap response", exc_info=True, extra={
                "token_id": token_id,
                "correlation_id": correlation_id
            })
            raise SDKError(error_msg, {
                "token_id": token_id,
                "error_type": type(e).__name__,
                "correlation_id": correlation_id
            })
            
        except Exception as e:
            error_msg = f"Unexpected error fetching token price: {str(e)}"
            logger.error("❌ Unexpected SaucerSwap error", exc_info=True, extra={
                "token_id": token_id,
                "correlation_id": correlation_id
            })
            raise SDKError(error_msg, {
                "token_id": token_id,
                "error_type": type(e).__name__,
                "correlation_id": correlation_id
            })
    
    async def get_hbar_price(self, correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Convenience method to get current HBAR price in USD.
        
        Args:
            correlation_id: Optional correlation ID for request tracking
            
        Returns:
            Same format as get_token_price() but specifically for HBAR
        """
        return await self.get_token_price(settings.hbar_token_id, correlation_id)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("🔒 SaucerSwap service closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()