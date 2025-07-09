"""
Custom exceptions for the AI Explorer backend service.
"""


class LLMServiceError(Exception):
    """
    Exception raised when the LLM service is unavailable or fails.
    
    This exception is used to signal that the external LLM service
    (OpenAI via LangChain) is experiencing issues and cannot process
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