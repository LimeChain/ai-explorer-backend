"""
Constants for chat service operations.
"""
from enum import Enum

# Length limits
MAX_SESSION_ID_LENGTH = 255
MAX_ACCOUNT_ID_LENGTH = 255
MAX_MESSAGE_CONTENT_LENGTH = 100000  # 100KB
MAX_CONVERSATION_LIMIT = 1000

# Message roles
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

# Default values
DEFAULT_CONVERSATION_LIMIT = 50