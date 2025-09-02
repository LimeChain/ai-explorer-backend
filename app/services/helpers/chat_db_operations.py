"""
Database operation utilities for chat service.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError
from app.utils.logging_config import get_service_logger

logger = get_service_logger("chat")


class ChatDBOperations:
    """Database operations for chat service."""
    
    @staticmethod
    def find_conversation_by_session(db: Session, session_id: UUID) -> Optional[Conversation]:
        """Find conversation by session ID."""
        try:
            return db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error finding conversation: {e}")
            raise ChatServiceError("Database error occurred while finding conversation", e) from e
    
    @staticmethod
    def create_conversation(db: Session, session_id: UUID, account_id: Optional[str]) -> Conversation:
        """Create new conversation."""
        try:
            conversation = Conversation(
                session_id=session_id,
                account_id=account_id
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            logger.debug(f"Created new conversation (ID: {conversation.id}) with session_id: {session_id}")
            return conversation
        except IntegrityError as e:
            logger.error(f"Integrity constraint error creating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Failed to create conversation due to data constraints", e) from e
        except SQLAlchemyError as e:
            logger.error(f"Database error creating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while creating conversation", e) from e
    
    @staticmethod
    def update_conversation_account(db: Session, conversation: Conversation, account_id: str) -> None:
        """Update conversation account ID."""
        try:
            conversation.account_id = account_id
            db.commit()
            logger.debug(f"Updated account_id for conversation {conversation.id}")
        except SQLAlchemyError as e:
            logger.error(f"Database error updating conversation: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while updating conversation", e) from e
    
    @staticmethod
    def create_message(db: Session, conversation_id: UUID, role: str, content: str) -> Message:
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
            logger.debug(f"Added {role} message (ID: {message.id}) to conversation {conversation_id}")
            return message
        except IntegrityError as e:
            logger.error(f"Integrity constraint error creating message: {e}")
            db.rollback()
            raise ChatServiceError("Failed to add message due to data constraints", e) from e
        except SQLAlchemyError as e:
            logger.error(f"Database error creating message: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while adding message", e) from e
    
    @staticmethod
    def get_conversation_messages(db: Session, conversation_id: UUID, limit: int, continue_from_message_id: Optional[UUID] = None) -> List[Message]:
        """Get messages for a conversation."""
        try:
            filters = [Message.conversation_id == conversation_id]
            if continue_from_message_id:
                message = db.query(Message).filter(
                    Message.id == continue_from_message_id,
                    Message.conversation_id == conversation_id
                ).first()
                if not message:
                    raise ChatServiceError(f"Message with ID {continue_from_message_id} not found in conversation {conversation_id}")
                filters.append(Message.created_at <= message.created_at)
            query = db.query(Message).filter(*filters).order_by(Message.created_at.asc())
            
            return query.limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving messages: {e}")
            raise ChatServiceError("Database error occurred while retrieving messages", e) from e
    
    @staticmethod
    def conversation_exists(db: Session, conversation_id: UUID) -> bool:
        """Check if conversation exists."""
        try:
            return db.query(Conversation).filter(Conversation.id == conversation_id).first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Database error checking conversation existence: {e}")
            raise ChatServiceError("Database error occurred while checking conversation", e) from e
    
    @staticmethod
    def messages_to_chat_messages(messages: List[Message]) -> List[ChatMessage]:
        """Convert database messages to ChatMessage schema."""
        return [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in messages
        ]
    
    @staticmethod
    def edit_message_and_delete_after(db: Session, message_id: UUID, new_content: str) -> tuple[Message, int]:
        """Atomically update message content and delete subsequent messages in the same conversation."""
        try:
            message = db.query(Message).filter(Message.id == message_id).with_for_update().first()
            if not message:
                raise ChatServiceError(f"Message with ID {message_id} not found")
            pivot_ts = message.created_at
            conv_id = message.conversation_id
            message.content = new_content
            message.edited_at = func.now()
            deleted_count = db.query(Message).filter(
                Message.conversation_id == conv_id,
                Message.created_at > pivot_ts
            ).delete(synchronize_session=False)
            db.commit()
            db.refresh(message)
            return message, deleted_count
        except SQLAlchemyError as e:
            logger.error(f"Database error editing message and deleting subsequent: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while editing message", e) from e
    
    @staticmethod
    def get_message_by_id(db: Session, message_id: UUID) -> Optional[Message]:
        """Get a specific message by ID."""
        try:
            return db.query(Message).filter(Message.id == message_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving message: {e}")
            raise ChatServiceError("Database error occurred while retrieving message", e) from e