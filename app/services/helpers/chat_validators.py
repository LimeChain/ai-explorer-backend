"""
Validation utilities for chat service operations.
"""
from typing import Optional

from app.exceptions import ValidationError
from app.services.helpers.chat_constants import (
    MAX_SESSION_ID_LENGTH, MAX_ACCOUNT_ID_LENGTH, MAX_MESSAGE_CONTENT_LENGTH,
    MAX_CONVERSATION_LIMIT, MessageRole
)


class ChatValidators:
    """Centralized validation logic for chat operations."""
    
    @staticmethod
    def validate_session_id(session_id: Optional[str]) -> str:
        """Validate session ID - required field."""
        if session_id is None:
            raise ValidationError("Session ID is required")
            
        if not isinstance(session_id, str) or len(session_id.strip()) == 0:
            raise ValidationError("Session ID must be a non-empty string")
            
        session_id = session_id.strip()
        if len(session_id) > MAX_SESSION_ID_LENGTH:
            raise ValidationError(f"Session ID too long (max {MAX_SESSION_ID_LENGTH} characters)")
            
        return session_id
    
    @staticmethod
    def validate_account_id(account_id: Optional[str]) -> Optional[str]:
        """Validate account ID format."""
        if account_id is None:
            return None
            
        if not isinstance(account_id, str):
            raise ValidationError("Account ID must be a string")
            
        account_id = account_id.strip()
        if len(account_id) == 0:
            return None
            
        if len(account_id) > MAX_ACCOUNT_ID_LENGTH:
            raise ValidationError(f"Account ID too long (max {MAX_ACCOUNT_ID_LENGTH} characters)")
            
        return account_id
    
    @staticmethod
    def validate_message_content(content: str, role: str) -> str:
        """Validate message content."""
        if not isinstance(content, str):
            raise ValidationError(f"Message content must be a string for role '{role}'")
            
        content = content.strip()
        if len(content) == 0:
            raise ValidationError(f"Message content cannot be empty for role '{role}'")
            
        if len(content) > MAX_MESSAGE_CONTENT_LENGTH:
            raise ValidationError(f"Message content too long for role '{role}' (max {MAX_MESSAGE_CONTENT_LENGTH//1000}KB)")
            
        return content
    
    @staticmethod
    def validate_message_role(role: str) -> str:
        """Validate message role."""
        if role not in [MessageRole.USER, MessageRole.ASSISTANT]:
            raise ValidationError(f"Invalid role: {role}. Must be '{MessageRole.USER}' or '{MessageRole.ASSISTANT}'")
        return role
    
    @staticmethod
    def validate_conversation_id(conversation_id: int) -> int:
        """Validate conversation ID."""
        if not isinstance(conversation_id, int) or conversation_id <= 0:
            raise ValidationError("Conversation ID must be a positive integer")
        return conversation_id
    
    @staticmethod
    def validate_limit(limit: int) -> int:
        """Validate conversation history limit."""
        if not isinstance(limit, int) or limit <= 0:
            raise ValidationError("Limit must be a positive integer")
        
        if limit > MAX_CONVERSATION_LIMIT:
            raise ValidationError(f"Limit too large (max {MAX_CONVERSATION_LIMIT} messages)")
        
        return limit