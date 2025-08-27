"""
Constants for all services.
"""
from enum import Enum

# === LLM Orchestration Constants ===

# Query and iteration limits
MAX_QUERY_LENGTH = 1000
MAX_ITERATIONS = 8
MAX_TOOL_CONTEXT_ITEMS = 5
MAX_CHAT_HISTORY_MESSAGES = 15

# LLM configuration
DEFAULT_TEMPERATURE = 0.1
RECURSION_LIMIT = 100

# Graph node names
class GraphNode(str, Enum):
    CALL_MODEL = "call_model"
    CALL_TOOL = "call_tool"
    END = "end"

# Tool names
class ToolName(str, Enum):
    CALL_SDK_METHOD = "call_sdk_method"
    RETRIEVE_SDK_METHOD = "retrieve_sdk_method"
    TEXT_TO_SQL_QUERY = "text_to_sql_query"
    CALCULATE_HBAR_VALUE = "calculate_hbar_value"
# === Chat Service Constants ===

# Length limits
MAX_ACCOUNT_ID_LENGTH = 255
MAX_MESSAGE_CONTENT_LENGTH = 100000  # 100KB
MAX_CONVERSATION_LIMIT = 1000

# Message roles
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

# Default values
DEFAULT_CONVERSATION_LIMIT = 50

# === Suggestion Service Constants ===

# Query limits
DEFAULT_SUGGESTION_LIMIT = 100
MAX_SUGGESTION_LIMIT = 500