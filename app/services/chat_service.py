"""
Chat Service for managing conversation persistence.

This service handles GDPR-compliant storage of chat conversations for internal
analysis and AI agent improvement while maintaining user privacy.
"""
import logging
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Conversation, Message
from app.db.session import get_session_local
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing chat history persistence.
    
    This service provides methods to:
    - Find or create conversation sessions
    - Store user and assistant messages
    - Retrieve conversation history
    - Maintain GDPR compliance with anonymous storage
    """
    
    def __init__(self):
        """Initialize the chat service."""
        self.SessionLocal = get_session_local()
    
    def find_or_create_conversation(
        self, 
        session_id: Optional[str] = None, 
        account_id: Optional[str] = None
    ) -> Conversation:
        """
        Find existing conversation or create a new one.
        
        Args:
            session_id: Optional client-provided session identifier
            account_id: Optional account ID for personalized context
            
        Returns:
            Conversation: The found or created conversation record
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        db = self.SessionLocal()
        try:
            # Generate session_id if not provided
            if not session_id:
                session_id = str(uuid4()) # TODO: remove this at later stage when we will force client to send session_id with the call of the webhook
            
            # Try to find existing conversation
            conversation = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
            
            if conversation:
                logger.info(f"Found existing conversation for session_id: {session_id}")
                return conversation
            
            # Create new conversation
            conversation = Conversation(
                session_id=session_id,
                account_id=account_id
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            logger.info(f"Created new conversation with session_id: {session_id}")
            return conversation
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in find_or_create_conversation: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    def add_message(
        self, 
        conversation_id: int, 
        role: str, 
        content: str
    ) -> Message:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: ID of the conversation
            role: Role of the message sender ('user' or 'assistant')
            content: Content of the message
            
        Returns:
            Message: The created message record
            
        Raises:
            SQLAlchemyError: If database operation fails
            ValueError: If role is not 'user' or 'assistant'
        """
        if role not in ['user', 'assistant']:
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")
        
        db = self.SessionLocal()
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            
            logger.debug(f"Added {role} message to conversation {conversation_id}")
            return message
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in add_message: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 50
    ) -> List[ChatMessage]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List[ChatMessage]: List of messages in chronological order
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        db = self.SessionLocal()
        try:
            conversation = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
            
            if not conversation:
                logger.warning(f"No conversation found for session_id: {session_id}")
                return []
            
            messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.created_at.asc()).limit(limit).all()
            
            # Convert to ChatMessage schema
            chat_messages = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in messages
            ]
            
            logger.debug(f"Retrieved {len(chat_messages)} messages for session {session_id}")
            return chat_messages
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_conversation_history: {e}")
            raise
        finally:
            db.close()
    
    def save_conversation_turn(
        self, 
        session_id: Optional[str], 
        account_id: Optional[str], 
        user_message: str, 
        assistant_response: str
    ) -> str:
        """
        Save a complete conversation turn (user message + assistant response).
        
        This is a convenience method that combines finding/creating conversation
        and saving both messages in a single operation.
        
        Args:
            session_id: Optional session identifier
            account_id: Optional account ID for context
            user_message: The user's message
            assistant_response: The assistant's response
            
        Returns:
            str: The session_id used for the conversation
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            # Find or create conversation
            conversation = self.find_or_create_conversation(
                session_id=session_id,
                account_id=account_id
            )
            
            # Save user message
            self.add_message(
                conversation_id=conversation.id,
                role="user",
                content=user_message
            )
            
            # Save assistant response
            self.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_response
            )
            
            logger.info(f"Saved conversation turn for session: {conversation.session_id}")
            return conversation.session_id
            
        except Exception as e:
            logger.error(f"Error saving conversation turn: {e}")
            raise