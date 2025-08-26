"""
Chat-related Pydantic models for API request/response validation.
"""
from typing import Optional, Literal
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
        query: The user's natural language query (for backwards compatibility)
        account_id: Optional connected wallet address for personalized context
    """
    query: Optional[str] = Field(
        None, 
        description="User's natural language query (for single queries)", 
        min_length=1
    )
    account_id: Optional[str] = Field(
        None, 
        description="Connected wallet address (e.g., '0.0.12345') for personalized responses"
    )
    network: Literal["mainnet", "testnet"] = Field(
        default="mainnet",
        description="Blockchain network to use (mainnet or testnet)"
    )

    def model_post_init(self, __context: None) -> None:
        """Validate that either messages or query is provided."""
        if not self.query:
            raise ValueError("'query' must be provided")



class ChatResponse(BaseModel):
    """
    Response model for chat endpoint.
    
    Attributes:
        response: The AI Explorer's response to the user's query
    """
    response: str = Field(..., description="AI Explorer's response to the user's query")