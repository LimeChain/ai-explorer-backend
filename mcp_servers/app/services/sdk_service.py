"""Hedera Mirror Node SDK service wrapper for dynamic method calling."""

import json
import inspect

from typing import Any, Dict

from hiero_mirror import MirrorNodeClient
from hiero_mirror.async_client import AsyncMirrorNodeClient
from ..logging_config import get_service_logger
from ..exceptions import (
    SDKError, 
    SDKMethodNotFoundError, 
    SDKParameterError, 
    SDKExecutionError,
    ConfigurationError
)

logger = get_service_logger("sdk_service", "mcp")


class HederaSDKService:
    """Service wrapper for dynamic Hedera Mirror Node SDK method calling."""
    
    def __init__(self, client: AsyncMirrorNodeClient | MirrorNodeClient):
        """Initialize the SDK service with configuration."""
        self.client = client
    
    async def call_method(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """
        Dynamically call any SDK method with the provided parameters.
        
        Args:
            method_name: The name of the SDK method to call
            **kwargs: Parameters to pass to the method
            
        Returns:
            Dict containing the method result or error information
        """
        import time
        start_time = time.time()
        logger.info("🌐 Mirror API: %s", method_name, extra={"params": list(kwargs.keys())})
        
        try:
            # Validate method exists
            if not hasattr(self.client, method_name):
                available_methods = self.get_available_methods()
                logger.warning("⚠️ SDK method not found", extra={
                    "method_name": method_name,
                    "available_methods": available_methods
                })
                raise SDKMethodNotFoundError(method_name, available_methods)
            
            method = getattr(self.client, method_name)
            
            # Validate method is callable
            if not callable(method):
                logger.warning("⚠️ SDK attribute is not callable", extra={
                    "method_name": method_name,
                    "attribute_type": type(method).__name__
                })
                raise SDKMethodNotFoundError(method_name)
            
            # Process and filter parameters
            filtered_kwargs = self._process_parameters(kwargs)
            logger.debug("⚙️ Processed parameters: %s", filtered_kwargs)
            
            # Execute method
            logger.debug("🚀 Executing %s with parameters: %s", method_name, filtered_kwargs)
            if inspect.iscoroutinefunction(method):
                result = await method(**filtered_kwargs)
            else:
                result = method(**filtered_kwargs)
            
            response_time = round((time.time() - start_time) * 1000, 2)
            logger.info("✅ %s", method_name, extra={"response_time_ms": response_time, "result_size": len(str(result)) if result else 0})
            
            return {
                "success": True,
                "data": result,
                "method_called": method_name,
                "parameters_used": filtered_kwargs
            }
            
        except SDKMethodNotFoundError:
            # Re-raise custom exceptions
            raise
        except TypeError as e:
            logger.error("❌ Parameter type error calling SDK method", exc_info=True, extra={
                "method_name": method_name,
                "parameters": locals().get('filtered_kwargs', kwargs)
            })
            raise SDKParameterError(method_name, str(e), locals().get('filtered_kwargs', kwargs)) from e
        except json.JSONDecodeError as e:
            logger.error("❌ JSON parsing error in SDK parameters", exc_info=True, extra={
                "method_name": method_name,
                "raw_kwargs": kwargs
            })
            raise SDKParameterError(method_name, f"Invalid JSON in kwargs parameter: {e}", kwargs) from e
        except Exception as e:
            logger.error("❌ Unexpected error calling SDK method", exc_info=True, extra={
                "method_name": method_name,
                "parameters": locals().get('filtered_kwargs', kwargs)
            })
            raise SDKExecutionError(method_name, str(e), locals().get('filtered_kwargs', kwargs), e) from e
    
    def _process_parameters(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and filter parameters for SDK method calls.
        
        Args:
            kwargs: Raw parameters received
            
        Returns:
            Filtered and processed parameters
        """
        filtered_kwargs = {}
        
        for k, v in kwargs.items():
            if k == "kwargs":
                # Handle nested kwargs parameter
                if isinstance(v, dict):
                    filtered_kwargs.update(v)
                elif isinstance(v, str) and v.strip():
                    try:
                        parsed_kwargs = json.loads(v)
                        if isinstance(parsed_kwargs, dict):
                            filtered_kwargs.update(parsed_kwargs)
                        else:
                            logger.warning("⚠️ Parsed kwargs is not a dict: %s", parsed_kwargs)
                    except json.JSONDecodeError as e:
                        logger.error("❌ Failed to parse kwargs JSON '%s': %s", v, e)
                        raise
            elif k != "kwargs" and v is not None and v != "":
                filtered_kwargs[k] = v
        return filtered_kwargs
    
    def get_available_methods(self) -> list:
        """Get a list of all available public methods in the SDK client."""
        methods = []
        for name in dir(self.client):
            if not name.startswith('_') and callable(getattr(self.client, name)):
                methods.append(name)
        return methods
    
    def get_method_signature(self, method_name: str) -> Dict[str, Any]:
        """Get the signature information for a specific method."""
        if not hasattr(self.client, method_name):
            return {"error": f"Method '{method_name}' not found"}
        
        method = getattr(self.client, method_name)
        if not callable(method):
            return {"error": f"'{method_name}' is not callable"}
        
        try:
            sig = inspect.signature(method)
            return {
                "method_name": method_name,
                "parameters": {
                    name: {
                        "annotation": str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
                        "default": param.default if param.default != inspect.Parameter.empty else None,
                        "kind": str(param.kind)
                    }
                    for name, param in sig.parameters.items()
                },
                "return_annotation": str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else None
            }
        except Exception as e:
            return {"error": f"Could not get signature for '{method_name}': {str(e)}"}