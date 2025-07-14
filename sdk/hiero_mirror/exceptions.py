"""Exception classes for the Hiero Mirror Node SDK."""

from typing import Any, Dict, List, Optional


class MirrorNodeException(Exception):
    """Base exception for all Mirror Node API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', status_code={self.status_code})"


class BadRequestError(MirrorNodeException):
    """Raised when the API returns a 400 Bad Request error."""

    def __init__(
        self,
        message: str = "Bad Request",
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, 400, response_data)


class NotFoundError(MirrorNodeException):
    """Raised when the API returns a 404 Not Found error."""

    def __init__(
        self,
        message: str = "Not Found",
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, 404, response_data)


class TooManyRequestsError(MirrorNodeException):
    """Raised when the API returns a 429 Too Many Requests error."""

    def __init__(
        self,
        message: str = "Too Many Requests",
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, 429, response_data)


class ServiceUnavailableError(MirrorNodeException):
    """Raised when the API returns a 500 or 503 Service Unavailable error."""

    def __init__(
        self,
        message: str = "Service Unavailable",
        status_code: int = 503,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code, response_data)


class ValidationError(MirrorNodeException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        super().__init__(message, None, {"field": field, "value": value})
        self.field = field
        self.value = value


class NetworkError(MirrorNodeException):
    """Raised when a network error occurs."""

    def __init__(
        self,
        message: str = "Network Error",
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, None, {"original_error": str(original_error)})
        self.original_error = original_error


class TimeoutError(MirrorNodeException):
    """Raised when a request times out."""

    def __init__(
        self,
        message: str = "Request Timeout",
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(message, None, {"timeout": timeout})
        self.timeout = timeout


def create_exception_from_response(
    status_code: int, response_data: Optional[Dict[str, Any]] = None
) -> MirrorNodeException:
    """Create an appropriate exception based on the HTTP status code."""
    message = "Unknown error"
    
    if response_data and "_status" in response_data:
        status_info = response_data["_status"]
        if "messages" in status_info and status_info["messages"]:
            # Extract the first message
            first_message = status_info["messages"][0]
            message = first_message.get("message", message)
    
    if status_code == 400:
        return BadRequestError(message, response_data)
    elif status_code == 404:
        return NotFoundError(message, response_data)
    elif status_code == 429:
        return TooManyRequestsError(message, response_data)
    elif status_code >= 500:
        return ServiceUnavailableError(message, status_code, response_data)
    else:
        return MirrorNodeException(message, status_code, response_data)


def extract_error_messages(response_data: Optional[Dict[str, Any]]) -> List[str]:
    """Extract error messages from API response data."""
    messages = []
    
    if response_data and "_status" in response_data:
        status_info = response_data["_status"]
        if "messages" in status_info and isinstance(status_info["messages"], list):
            for msg in status_info["messages"]:
                if isinstance(msg, dict) and "message" in msg:
                    messages.append(msg["message"])
                elif isinstance(msg, str):
                    messages.append(msg)
    
    return messages