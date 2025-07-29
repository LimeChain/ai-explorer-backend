"""
Chat-related Pydantic models for API request/response validation.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    Individual chat message model.
    
    Attributes:
        role: The role of the message sender ('user' or 'assistant')
        content: The content of the message
    """
    role: str = Field(..., description="Role of the message sender", pattern="^(user|assistant)$")
    content: str = Field(..., description="Content of the message", min_length=1)


class ChatRequest(BaseModel):
    """
    Request model for chat endpoint.
    
    Attributes:
        messages: List of conversation messages (supports multi-turn conversations)
        query: The user's natural language query (for backwards compatibility)
        account_id: Optional connected wallet address for personalized context
        session_id: Optional client-generated session identifier for traceability
    """
    messages: Optional[List[ChatMessage]] = Field(
        None, 
        description="List of conversation messages for multi-turn chat"
    )
    query: Optional[str] = Field(
        None, 
        description="User's natural language query (for single queries)", 
        min_length=1
    )
    account_id: Optional[str] = Field(
        None, 
        description="Connected wallet address (e.g., '0.0.12345') for personalized responses"
    )
    session_id: Optional[str] = Field(
        None, 
        description="Client-generated session identifier for request traceability"
    )
    
    def model_post_init(self, __context: None) -> None:
        """Validate that either messages or query is provided."""
        if not self.messages and not self.query:
            raise ValueError("Either 'messages' or 'query' must be provided")
        
        # Convert single query to messages format for internal processing
        if self.query and not self.messages:
            self.messages = [ChatMessage(role="user", content=self.query)]


class ChatResponse(BaseModel):
    """
    Response model for chat endpoint.
    
    Attributes:
        response: The AI Explorer's response to the user's query
    """
    response: str = Field(..., description="AI Explorer's response to the user's query")