"""Hedera Mirror Node SDK service wrapper for dynamic method calling."""

import json
import logging
import inspect

from typing import Any, Dict
from hiero_mirror import MirrorNodeClient

logger = logging.getLogger(__name__)


class HederaSDKService:
    """Service wrapper for dynamic Hedera Mirror Node SDK method calling."""
    
    def __init__(self):
        """Initialize the SDK service with configuration."""
        try:
            self.client = MirrorNodeClient.for_testnet() # TODO: Make this configurable to support mainnet or other networks
            logger.info("Successfully initialized Hedera SDK service for testnet")
        except Exception as e:
            logger.error(f"Failed to initialize Hedera SDK service: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Hedera SDK service: {e}") from e
    
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
                error_msg = f"Method '{method_name}' not found in SDK"
                logger.warning(error_msg)
                available_methods = self.get_available_methods()
                return {
                    "error": error_msg,
                    "available_methods": available_methods,
                    "method_called": method_name,
                    "parameters_used": kwargs
                }
            
            method = getattr(self.client, method_name)
            
            # Validate method is callable
            if not callable(method):
                error_msg = f"'{method_name}' is not a callable method"
                logger.warning(error_msg)
                return {
                    "error": error_msg,
                    "method_called": method_name,
                    "parameters_used": kwargs
                }
            
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
            
        except TypeError as e:
            error_msg = str(e)
            logger.error(f"Parameter error calling {method_name}: {error_msg}")
            logger.debug(f"Parameters that caused error: {locals().get('filtered_kwargs', kwargs)}")
            return {
                "error": error_msg,
                "method_called": method_name,
                "parameters_used": locals().get('filtered_kwargs', kwargs),
                "error_type": "TypeError",
                "hint": "Check method signature and ensure all required parameters are provided"
            }
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in kwargs parameter: {e}"
            logger.error(f"JSON parsing error for {method_name}: {error_msg}")
            return {
                "error": error_msg,
                "method_called": method_name,
                "parameters_used": kwargs,
                "error_type": "JSONDecodeError"
            }
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(f"Unexpected error calling {method_name}: {error_msg}", exc_info=True)
            return {
                "error": error_msg,
                "method_called": method_name,
                "parameters_used": locals().get('filtered_kwargs', kwargs),
                "error_type": error_type
            }
    
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