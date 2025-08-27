"""
Custom exception hierarchy for the MCP server.
Provides structured error handling with proper categorization and context.
"""
from typing import Optional, Dict, Any


class MCPServerError(Exception):
    """Base exception for all MCP server errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        result = {
            "error": self.error_code,
            "message": self.message,
            "success": False
        }
        if self.context:
            result["context"] = self.context
        if self.cause:
            result["cause"] = str(self.cause)
        return result


class ValidationError(MCPServerError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)
        super().__init__(message, "ValidationError", context)


class ConfigurationError(MCPServerError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None):
        context = {"config_key": config_key} if config_key else {}
        super().__init__(message, "ConfigurationError", context)


class ServiceInitializationError(MCPServerError):
    """Raised when a service fails to initialize properly."""
    
    def __init__(self, service_name: str, message: str, cause: Optional[Exception] = None):
        context = {"service": service_name}
        super().__init__(f"{service_name} initialization failed: {message}", "ServiceInitializationError", context, cause)


# SDK-related exceptions
class SDKError(MCPServerError):
    """Base exception for SDK-related errors."""
    pass


class SDKMethodNotFoundError(SDKError):
    """Raised when a requested SDK method is not found."""
    
    def __init__(self, method_name: str, available_methods: Optional[list] = None):
        context = {"method_name": method_name}
        if available_methods:
            context["available_methods"] = available_methods
        super().__init__(f"SDK method '{method_name}' not found", "SDKMethodNotFoundError", context)


class SDKParameterError(SDKError):
    """Raised when SDK method parameters are invalid."""
    
    def __init__(self, method_name: str, message: str, parameters: Optional[Dict] = None):
        context = {"method_name": method_name}
        if parameters:
            context["parameters"] = parameters
        super().__init__(f"Parameter error for '{method_name}': {message}", "SDKParameterError", context)


class SDKExecutionError(SDKError):
    """Raised when SDK method execution fails."""
    
    def __init__(self, method_name: str, message: str, parameters: Optional[Dict] = None, cause: Optional[Exception] = None):
        context = {"method_name": method_name}
        if parameters:
            context["parameters"] = parameters
        super().__init__(f"Execution error for '{method_name}': {message}", "SDKExecutionError", context, cause)


# Database-related exceptions
class DatabaseError(MCPServerError):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    
    def __init__(self, message: str, connection_string: Optional[str] = None, cause: Optional[Exception] = None):
        context = {}
        if connection_string:
            # Don't log full connection string for security
            context["connection_host"] = connection_string.split('@')[-1].split('/')[0] if '@' in connection_string else "unknown"
        super().__init__(f"Database connection failed: {message}", "DatabaseConnectionError", context, cause)


class DatabaseOperationError(DatabaseError):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, message: str, cause: Optional[Exception] = None):
        context = {"operation": operation}
        super().__init__(f"Database operation '{operation}' failed: {message}", "DatabaseOperationError", context, cause)


# Vector store-related exceptions
class VectorStoreError(MCPServerError):
    """Base exception for vector store operations."""
    pass


class VectorStoreInitializationError(VectorStoreError):
    """Raised when vector store initialization fails."""
    
    def __init__(self, message: str, collection_name: Optional[str] = None, cause: Optional[Exception] = None):
        context = {"collection_name": collection_name} if collection_name else {}
        super().__init__(f"Vector store initialization failed: {message}", "VectorStoreInitializationError", context, cause)


class VectorStoreSearchError(VectorStoreError):
    """Raised when vector similarity search fails."""
    
    def __init__(self, query: str, message: str, cause: Optional[Exception] = None):
        context = {"query": query}
        super().__init__(f"Vector search failed: {message}", "VectorStoreSearchError", context, cause)


class EmbeddingError(VectorStoreError):
    """Raised when embedding generation fails."""
    
    def __init__(self, text: str, message: str, cause: Optional[Exception] = None):
        context = {"text_length": len(text) if text else 0}
        super().__init__(f"Embedding generation failed: {message}", "EmbeddingError", context, cause)


class DocumentProcessingError(VectorStoreError):
    """Raised when document processing fails."""
    
    def __init__(self, document_path: Optional[str], message: str, cause: Optional[Exception] = None):
        context = {"document_path": document_path} if document_path else {}
        super().__init__(f"Document processing failed: {message}", "DocumentProcessingError", context, cause)


# External API-related exceptions
class ExternalAPIError(MCPServerError):
    """Base exception for external API errors."""
    pass


class OpenAIAPIError(ExternalAPIError):
    """Raised when OpenAI API calls fail."""
    
    def __init__(self, message: str, model: Optional[str] = None, cause: Optional[Exception] = None):
        context = {"model": model} if model else {}
        super().__init__(f"OpenAI API error: {message}", "OpenAIAPIError", context, cause)


class HederaAPIError(ExternalAPIError):
    """Raised when Hedera API calls fail."""
    
    def __init__(self, message: str, endpoint: Optional[str] = None, cause: Optional[Exception] = None):
        context = {"endpoint": endpoint} if endpoint else {}
        super().__init__(f"Hedera API error: {message}", "HederaAPIError", context, cause)


def handle_exception(exc: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert any exception to a standardized error response.
    
    Args:
        exc: The exception to handle
        context: Additional context information
        
    Returns:
        Standardized error response dictionary
    """
    if isinstance(exc, MCPServerError):
        error_dict = exc.to_dict()
        if context:
            error_dict["context"].update(context)
        return error_dict
    
    # Handle standard Python exceptions
    error_dict = {
        "error": exc.__class__.__name__,
        "message": str(exc),
        "success": False
    }
    
    if context:
        error_dict["context"] = context
    
    return error_dict