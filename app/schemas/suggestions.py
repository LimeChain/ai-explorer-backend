"""
Suggestion-related Pydantic models for API request/response validation.
"""
from typing import List
from enum import Enum
from pydantic import BaseModel, Field


class SuggestionContext(str, Enum):
    """
    Enumeration for suggestion contexts.
    
    Values:
        ANONYMOUS: User is not connected to a wallet
        CONNECTED: User has a connected wallet
    """
    ANONYMOUS = "anonymous"
    CONNECTED = "connected"


class SuggestedQuery(BaseModel):
    """
    Individual suggested query model.
    
    Attributes:
        query: The suggested query text
    """
    query: str = Field(..., description="The suggested query text", min_length=1)


class SuggestedQueriesResponse(BaseModel):
    """
    Response model for suggested queries endpoint.
    
    Attributes:
        suggestions: List of suggested queries
    """
    suggestions: List[SuggestedQuery] = Field(..., description="List of suggested queries")