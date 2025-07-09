"""
Global exception handlers for the AI Explorer backend service.
"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse

from app.exceptions import LLMServiceError, ValidationError


logger = logging.getLogger(__name__)


async def llm_service_error_handler(request: Request, exc: LLMServiceError) -> JSONResponse:
    """
    Global exception handler for LLM service errors.
    
    This handler catches LLMServiceError exceptions raised anywhere in the application
    and converts them into a standardized HTTP 503 Service Unavailable response.
    This ensures consistent error responses when the AI service is unavailable.
    
    Args:
        request: The incoming HTTP request
        exc: The LLMServiceError exception that was raised
        
    Returns:
        JSONResponse with 503 status and error details
    """
    logger.error(f"LLM service error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)}
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Global exception handler for validation errors.
    
    This handler catches ValidationError exceptions and converts them into
    a standardized HTTP 400 Bad Request response.
    
    Args:
        request: The incoming HTTP request
        exc: The ValidationError exception that was raised
        
    Returns:
        JSONResponse with 400 status and error details
    """
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI application.
    
    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(LLMServiceError, llm_service_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)