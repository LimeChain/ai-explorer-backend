"""
Chat-related Pydantic models for API request/response validation.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint.
    
    Attributes:
        query: The user's natural language query to the AI Explorer
    """
    query: str = Field(..., description="User's natural language query", min_length=1)


class ChatResponse(BaseModel):
    """
    Response model for chat endpoint.
    
    Attributes:
        response: The AI Explorer's response to the user's query
    """
    response: str = Field(..., description="AI Explorer's response to the user's query")