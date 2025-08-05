"""
Custom exceptions for the AI Explorer backend service.
"""


class LLMServiceError(Exception):
    """
    Exception raised when the LLM service is unavailable or fails.
    
    This exception is used to signal that the external LLM service
    (LLM service via LangChain) is experiencing issues and cannot process
    the user's request at this time.
    
    Args:
        message: Human-readable error message to display to users
    """
    pass


class ValidationError(Exception):
    """
    Exception raised when input validation fails.
    
    This exception is used to signal that user input does not meet
    the required validation criteria.
    
    Args:
        message: Human-readable error message describing the validation failure
    """
    pass


class DatabaseError(Exception):
    """
    Exception raised when database operations fail.
    
    This exception wraps SQLAlchemy exceptions and provides
    application-specific error handling for database operations.
    
    Args:
        message: Human-readable error message
        original_error: The original exception that caused this error
    """
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error


class ChatServiceError(DatabaseError):
    """
    Exception raised when chat service operations fail.
    
    Specific to chat-related database operations like conversation
    management and message persistence.
    """
    pass


class SuggestionServiceError(DatabaseError):
    """
    Exception raised when suggestion service operations fail.
    
    Specific to suggestion-related database operations.
    """
    pass


class SessionNotFoundError(DatabaseError):
    """
    Exception raised when a requested session is not found.
    
    Used when trying to retrieve conversation history or messages
    for a non-existent session.
    """
    pass

class RateLimitError(Exception):
    """
    Exception raised when a rate limit is exceeded.
    """
    pass