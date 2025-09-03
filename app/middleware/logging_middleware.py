"""
Logging middleware for correlation ID tracking and request logging.
"""
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from app.utils.logging_config import set_correlation_id, get_correlation_id, get_api_logger
import time

logger = get_api_logger(__name__)


async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware to add correlation ID to all requests and log request/response info.
    
    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain
        
    Returns:
        Response with correlation ID header
    """
    # Generate or extract correlation ID
    correlation_id = request.headers.get("x-correlation-id")
    if not correlation_id:
        correlation_id = set_correlation_id()
    else:
        set_correlation_id(correlation_id)
    
    # Log incoming request
    start_time = time.time()
    logger.info(
        "➡️ Incoming request",
        extra={
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Add correlation ID to response headers
    if hasattr(response, 'headers'):
        response.headers["x-correlation-id"] = get_correlation_id()
    
    response_info = {
        "method": request.method,
        "path": str(request.url.path),
        "status_code": response.status_code if hasattr(response, 'status_code') else None,
        "process_time_seconds": round(process_time, 4),
    }
    
    # Add response size info only if available without loading body
    if hasattr(response, 'headers'):
        content_length = response.headers.get("content-length")
        if content_length:
            response_info["response_size_bytes"] = int(content_length)
    
    # Identify streaming responses
    if isinstance(response, StreamingResponse):
        response_info["response_type"] = "streaming"
    
    logger.info("Request completed", extra=response_info)
    
    return response
