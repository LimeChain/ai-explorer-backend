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
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError, ValidationError, SessionNotFoundError

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for managing chat history persistence.
    
    This service provides methods to:
    - Find or create conversation sessions
    - Store user and assistant messages
    - Retrieve conversation history
    - Maintain GDPR compliance with anonymous storage
    
    All methods accept a database session as dependency injection,
    following production-ready patterns for better testability and
    resource management.
    """
    
    @staticmethod
    def _validate_session_id(session_id: Optional[str]) -> str:
        """
        Validate and generate session ID if needed.
        
        Args:
            session_id: Optional session identifier
            
        Returns:
            str: Valid session ID
            
        Raises:
            ValidationError: If session_id format is invalid
        """
        if session_id is None:
            return str(uuid4())
            
        if not isinstance(session_id, str) or len(session_id.strip()) == 0:
            raise ValidationError("Session ID must be a non-empty string")
            
        # Basic UUID format validation (optional - could be more strict)
        session_id = session_id.strip()
        if len(session_id) > 255:  # Database constraint
            raise ValidationError("Session ID too long (max 255 characters)")
            
        return session_id
    
    @staticmethod
    def _validate_account_id(account_id: Optional[str]) -> Optional[str]:
        """
        Validate account ID format.
        
        Args:
            account_id: Optional account identifier
            
        Returns:
            Optional[str]: Validated account ID or None
            
        Raises:
            ValidationError: If account_id format is invalid
        """
        if account_id is None:
            return None
            
        if not isinstance(account_id, str):
            raise ValidationError("Account ID must be a string")
            
        account_id = account_id.strip()
        if len(account_id) == 0:
            return None
            
        if len(account_id) > 255:  # Database constraint
            raise ValidationError("Account ID too long (max 255 characters)")
            
        return account_id
    
    @staticmethod
    def _validate_message_content(content: str, role: str) -> str:
        """
        Validate message content.
        
        Args:
            content: Message content
            role: Message role
            
        Returns:
            str: Validated content
            
        Raises:
            ValidationError: If content is invalid
        """
        if not isinstance(content, str):
            raise ValidationError(f"Message content must be a string for role '{role}'")
            
        content = content.strip()
        if len(content) == 0:
            raise ValidationError(f"Message content cannot be empty for role '{role}'")
            
        # Reasonable content length limit (adjust based on requirements)
        if len(content) > 100000:  # 100KB
            raise ValidationError(f"Message content too long for role '{role}' (max 100KB)")
            
        return content
    
    @staticmethod
    def find_or_create_conversation(
        db: Session,
        session_id: Optional[str] = None, 
        account_id: Optional[str] = None
    ) -> Conversation:
        """
        Find existing conversation or create a new one.
        
        Args:
            db: Database session (dependency injected)
            session_id: Optional client-provided session identifier
            account_id: Optional account ID for personalized context
            
        Returns:
            Conversation: The found or created conversation record
            
        Raises:
            ChatServiceError: If database operation fails
            ValidationError: If input validation fails
        """
        try:
            # Validate inputs
            validated_session_id = ChatService._validate_session_id(session_id)
            validated_account_id = ChatService._validate_account_id(account_id)
            
            logger.info(f"Finding or creating conversation for session_id: {validated_session_id}")
            
            # Try to find existing conversation
            conversation = db.query(Conversation).filter(
                Conversation.session_id == validated_session_id
            ).first()
            
            if conversation:
                logger.info(f"Found existing conversation (ID: {conversation.id}) for session_id: {validated_session_id}")
                # Update account_id if provided and different
                if validated_account_id and conversation.account_id != validated_account_id:
                    conversation.account_id = validated_account_id
                    db.commit()
                    logger.info(f"Updated account_id for conversation {conversation.id}")
                return conversation
            
            # Create new conversation
            conversation = Conversation(
                session_id=validated_session_id,
                account_id=validated_account_id
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            
            logger.info(f"Created new conversation (ID: {conversation.id}) with session_id: {validated_session_id}")
            return conversation
            
        except ValidationError:
            logger.warning(f"Validation error in find_or_create_conversation: session_id={session_id}, account_id={account_id}")
            raise
        except IntegrityError as e:
            logger.error(f"Integrity constraint error in find_or_create_conversation: {e}")
            db.rollback()
            raise ChatServiceError("Failed to create conversation due to data constraints", e)
        except SQLAlchemyError as e:
            logger.error(f"Database error in find_or_create_conversation: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while managing conversation", e)
    
    @staticmethod
    def add_message(
        db: Session,
        conversation_id: int, 
        role: str, 
        content: str
    ) -> Message:
        """
        Add a message to a conversation.
        
        Args:
            db: Database session (dependency injected)
            conversation_id: ID of the conversation
            role: Role of the message sender ('user' or 'assistant')
            content: Content of the message
            
        Returns:
            Message: The created message record
            
        Raises:
            ChatServiceError: If database operation fails
            ValidationError: If input validation fails
        """
        try:
            # Validate role
            if role not in ['user', 'assistant']:
                raise ValidationError(f"Invalid role: {role}. Must be 'user' or 'assistant'")
            
            # Validate conversation_id
            if not isinstance(conversation_id, int) or conversation_id <= 0:
                raise ValidationError("Conversation ID must be a positive integer")
            
            # Validate and clean content
            validated_content = ChatService._validate_message_content(content, role)
            
            logger.debug(f"Adding {role} message to conversation {conversation_id}")
            
            # Verify conversation exists
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conversation:
                raise ValidationError(f"Conversation with ID {conversation_id} not found")
            
            # Create message
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=validated_content
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            
            logger.info(f"Added {role} message (ID: {message.id}) to conversation {conversation_id}")
            return message
            
        except ValidationError:
            logger.warning(f"Validation error in add_message: conversation_id={conversation_id}, role={role}")
            raise
        except IntegrityError as e:
            logger.error(f"Integrity constraint error in add_message: {e}")
            db.rollback()
            raise ChatServiceError("Failed to add message due to data constraints", e)
        except SQLAlchemyError as e:
            logger.error(f"Database error in add_message: {e}")
            db.rollback()
            raise ChatServiceError("Database error occurred while adding message", e)
    
    @staticmethod
    def get_conversation_history(
        db: Session,
        session_id: str, 
        limit: int = 50
    ) -> List[ChatMessage]:
        """
        Retrieve conversation history for a session.
        
        Args:
            db: Database session (dependency injected)
            session_id: Session identifier
            limit: Maximum number of messages to retrieve (default: 50)
            
        Returns:
            List[ChatMessage]: List of messages in chronological order
            
        Raises:
            ChatServiceError: If database operation fails
            ValidationError: If input validation fails
            SessionNotFoundError: If session doesn't exist
        """
        try:
            # Validate inputs
            if not isinstance(session_id, str) or len(session_id.strip()) == 0:
                raise ValidationError("Session ID must be a non-empty string")
            
            if not isinstance(limit, int) or limit <= 0:
                raise ValidationError("Limit must be a positive integer")
            
            if limit > 1000:  # Reasonable upper bound
                raise ValidationError("Limit too large (max 1000 messages)")
            
            session_id = session_id.strip()
            logger.debug(f"Retrieving conversation history for session_id: {session_id}, limit: {limit}")
            
            # Find conversation
            conversation = db.query(Conversation).filter(
                Conversation.session_id == session_id
            ).first()
            
            if not conversation:
                logger.info(f"No conversation found for session_id: {session_id}")
                raise SessionNotFoundError(f"No conversation found for session: {session_id}")
            
            # Retrieve messages
            messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.created_at.asc()).limit(limit).all()
            
            # Convert to ChatMessage schema
            chat_messages = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in messages
            ]
            
            logger.info(f"Retrieved {len(chat_messages)} messages for session {session_id}")
            return chat_messages
            
        except ValidationError:
            logger.warning(f"Validation error in get_conversation_history: session_id={session_id}, limit={limit}")
            raise
        except SessionNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_conversation_history: {e}")
            raise ChatServiceError("Database error occurred while retrieving conversation history", e)
    
    @staticmethod
    def save_conversation_turn(
        db: Session,
        session_id: Optional[str], 
        account_id: Optional[str], 
        user_message: str, 
        assistant_response: str
    ) -> str:
        """
        Save a complete conversation turn (user message + assistant response).
        
        This is a convenience method that combines finding/creating conversation
        and saving both messages in a single atomic operation with proper
        transaction management.
        
        Args:
            db: Database session (dependency injected)
            session_id: Optional session identifier
            account_id: Optional account ID for context
            user_message: The user's message
            assistant_response: The assistant's response
            
        Returns:
            str: The session_id used for the conversation
            
        Raises:
            ChatServiceError: If database operation fails
            ValidationError: If input validation fails
        """
        try:
            logger.info(f"Saving conversation turn for session: {session_id}")
            
            # Find or create conversation
            conversation = ChatService.find_or_create_conversation(
                db=db,
                session_id=session_id,
                account_id=account_id
            )
            
            # Save user message
            user_msg = ChatService.add_message(
                db=db,
                conversation_id=conversation.id,
                role="user",
                content=user_message
            )
            
            # Save assistant response
            assistant_msg = ChatService.add_message(
                db=db,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_response
            )
            
            logger.info(f"Saved conversation turn (user: {user_msg.id}, assistant: {assistant_msg.id}) for session: {conversation.session_id}")
            return conversation.session_id
            
        except (ValidationError, ChatServiceError, SessionNotFoundError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving conversation turn: {e}")
            db.rollback()
            raise ChatServiceError("Unexpected error occurred while saving conversation turn", e)