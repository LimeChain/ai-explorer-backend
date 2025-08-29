"""
Global exception handlers for the AI Explorer backend service.
"""
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

from app.exceptions import LLMServiceError, ValidationError, RateLimitError
from app.utils.logging_config import get_logger

logger = get_logger(__name__, service_name="api")


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
    logger.error(f"❌ LLM service error: {exc}")
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
    # Security event logging for validation failures
    client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
    logger.warning("⚠️ Security event: Validation error", extra={
        "event_type": "validation_error",
        "client_ip": client_ip,
        "endpoint": f"{request.method} {request.url.path}",
        "user_agent": request.headers.get('user-agent', 'unknown'),
        "error_message": str(exc),
        "request_timestamp": request.state.__dict__.get('start_time', 0)
    })
    
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


async def rate_limit_error_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    """
    Global exception handler for rate limiting errors.
    
    This handler catches RateLimitError exceptions and converts them into
    a standardized HTTP 429 Too Many Requests response.
    
    Args:
        request: The incoming HTTP request
        exc: The RateLimitError exception that was raised
        
    Returns:
        JSONResponse with 429 status and error details
    """
    # Security event logging for rate limit violations
    client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
    logger.warning("🚨 Security event: Rate limit exceeded", extra={
        "event_type": "rate_limit_violation",
        "client_ip": client_ip,
        "endpoint": f"{request.method} {request.url.path}",
        "user_agent": request.headers.get('user-agent', 'unknown'),
        "error_message": str(exc),
        "request_timestamp": request.state.__dict__.get('start_time', 0)
    })
    
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI application.
    
    Args:
        app: The FastAPI application instance
    """
    app.add_exception_handler(LLMServiceError, llm_service_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(RateLimitError, rate_limit_error_handler)