"""
Database operation utilities for chat service.
"""
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError, SessionNotFoundError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChatDBOperations:
    """Database operations for chat service."""
    
    @staticmethod
    def find_conversation_by_session(db: Session, session_id: str) -> Optional[Conversation]:
        """Find conversation by session ID."""
        try:
            return db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error finding conversation: {e}")
            raise ChatServiceError("Database error occurred while finding conversation", e)
    
    @staticmethod
    def create_conversation(db: Session, session_id: str, account_id: Optional[str]) -> Conversation:
        """Create new conversation."""
        try:
            conversation = Conversation(
                session_id=session_id,
                account_id=account_id
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            logger.info(f"Created new conversation (ID: {conversation.id}) with session_id: {session_id}")
            return conversation
        except IntegrityError as e:
            logger.error(f"Integrity constraint error creating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Failed to create conversation due to data constraints", e)
        except SQLAlchemyError as e:
            logger.error(f"Database error creating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while creating conversation", e)
    
    @staticmethod
    def update_conversation_account(db: Session, conversation: Conversation, account_id: str) -> None:
        """Update conversation account ID."""
        try:
            conversation.account_id = account_id
            db.commit()
            logger.info(f"Updated account_id for conversation {conversation.id}")
        except SQLAlchemyError as e:
            logger.error(f"Database error updating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while updating conversation", e)
    
    @staticmethod
    def create_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
        """Create new message."""
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            logger.info(f"Added {role} message (ID: {message.id}) to conversation {conversation_id}")
            return message
        except IntegrityError as e:
            logger.error(f"Integrity constraint error creating message: {e}")
            db.rollback()
            raise ChatServiceError("Failed to add message due to data constraints", e)
        except SQLAlchemyError as e:
            logger.error(f"Database error creating message: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while adding message", e)
    
    @staticmethod
    def get_conversation_messages(db: Session, conversation_id: int, limit: int) -> List[Message]:
        """Get messages for a conversation."""
        try:
            return db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.asc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving messages: {e}")
            raise ChatServiceError("Database error occurred while retrieving messages", e)
    
    @staticmethod
    def conversation_exists(db: Session, conversation_id: int) -> bool:
        """Check if conversation exists."""
        try:
            return db.query(Conversation).filter(Conversation.id == conversation_id).first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Database error checking conversation existence: {e}")
            raise ChatServiceError("Database error occurred while checking conversation", e)
    
    @staticmethod
    def messages_to_chat_messages(messages: List[Message]) -> List[ChatMessage]:
        """Convert database messages to ChatMessage schema."""
        return [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in messages
        ]