"""Hedera Mirror Node SDK service wrapper for dynamic method calling."""

import json
import inspect

from typing import Any, Dict

from hiero_mirror import MirrorNodeClient
from ..logging_config import get_service_logger
from ..exceptions import (
    SDKError, 
    SDKMethodNotFoundError, 
    SDKParameterError, 
    SDKExecutionError,
    ConfigurationError
)

logger = get_service_logger("sdk_service")


class HederaSDKService:
    """Service wrapper for dynamic Hedera Mirror Node SDK method calling."""
    
    def __init__(self):
        """Initialize the SDK service with configuration."""
        try:
            self.client = MirrorNodeClient.for_testnet() # TODO: Make this configurable to support mainnet or other networks
            logger.info("Successfully initialized Hedera SDK service for testnet")
        except Exception as e:
            logger.error("Failed to initialize Hedera SDK service", exc_info=True, extra={
                "network": "testnet"
            })
            raise ConfigurationError(f"Failed to initialize Hedera SDK service: {e}", "hedera_network") from e
    
    async def call_method(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """
        Dynamically call any SDK method with the provided parameters.
        
        Args:
            method_name: The name of the SDK method to call
            **kwargs: Parameters to pass to the method
            
        Returns:
            Dict containing the method result or error information
        """
        logger.info(f"Calling SDK method: {method_name}")
        logger.debug(f"Raw parameters received: {kwargs}")
        
        try:
            # Validate method exists
            if not hasattr(self.client, method_name):
                available_methods = self.get_available_methods()
                logger.warning("SDK method not found", extra={
                    "method_name": method_name,
                    "available_methods": available_methods
                })
                raise SDKMethodNotFoundError(method_name, available_methods)
            
            method = getattr(self.client, method_name)
            
            # Validate method is callable
            if not callable(method):
                logger.warning("SDK attribute is not callable", extra={
                    "method_name": method_name,
                    "attribute_type": type(method).__name__
                })
                raise SDKMethodNotFoundError(method_name)
            
            # Process and filter parameters
            filtered_kwargs = self._process_parameters(kwargs)
            logger.debug(f"Processed parameters: {filtered_kwargs}")
            
            # Execute method
            logger.debug(f"Executing {method_name} with parameters: {filtered_kwargs}")
            if inspect.iscoroutinefunction(method):
                result = await method(**filtered_kwargs)
            else:
                result = method(**filtered_kwargs)
            
            logger.info(f"Successfully executed {method_name}")
            logger.debug(f"Method result type: {type(result)}")
            
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
            logger.error("Parameter type error calling SDK method", exc_info=True, extra={
                "method_name": method_name,
                "parameters": locals().get('filtered_kwargs', kwargs)
            })
            raise SDKParameterError(method_name, str(e), locals().get('filtered_kwargs', kwargs)) from e
        except json.JSONDecodeError as e:
            logger.error("JSON parsing error in SDK parameters", exc_info=True, extra={
                "method_name": method_name,
                "raw_kwargs": kwargs
            })
            raise SDKParameterError(method_name, f"Invalid JSON in kwargs parameter: {e}", kwargs) from e
        except Exception as e:
            logger.error("Unexpected error calling SDK method", exc_info=True, extra={
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
            logger.debug(f"Processing parameter '{k}' = '{v}' (type: {type(v)})")
            
            if k == "kwargs":
                # Handle nested kwargs parameter
                if isinstance(v, dict):
                    logger.debug(f"Found kwargs dict: {v}")
                    filtered_kwargs.update(v)
                elif isinstance(v, str) and v.strip():
                    logger.debug(f"Found kwargs JSON string: {v}")
                    try:
                        parsed_kwargs = json.loads(v)
                        if isinstance(parsed_kwargs, dict):
                            logger.debug(f"Successfully parsed kwargs: {parsed_kwargs}")
                            filtered_kwargs.update(parsed_kwargs)
                        else:
                            logger.warning(f"Parsed kwargs is not a dict: {parsed_kwargs}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse kwargs JSON '{v}': {e}")
                        raise
                else:
                    logger.debug(f"Skipping invalid kwargs: {v}")
            elif k != "kwargs" and v is not None and v != "":
                logger.debug(f"Adding regular parameter: {k} = {v}")
                filtered_kwargs[k] = v
            else:
                logger.debug(f"Skipping parameter '{k}' = '{v}' (empty or None)")
        
        logger.debug(f"Final processed parameters: {filtered_kwargs}")
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