"""
Constants for LLM orchestration.
"""
from enum import Enum

# Query and iteration limits
MAX_QUERY_LENGTH = 1000
MAX_ITERATIONS = 8
MAX_TOOL_CONTEXT_ITEMS = 5

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