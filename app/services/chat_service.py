"""
Chat Service for managing conversation persistence.

This service handles GDPR-compliant storage of chat conversations for internal
analysis and AI agent improvement while maintaining user privacy.
"""
import logging

from uuid import UUID
from typing import Optional, List

from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError, ValidationError, SessionNotFoundError
from app.services.helpers.chat_validators import ChatValidators
from app.services.helpers.chat_db_operations import ChatDBOperations
from app.services.helpers.constants import DEFAULT_CONVERSATION_LIMIT

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChatService:
    """Service for managing chat history persistence."""
    
    
    @staticmethod
    def find_or_create_conversation(
        db: Session,
        session_id: Optional[UUID] = None, 
        account_id: Optional[str] = None
    ) -> Conversation:
        """Find existing conversation or create a new one."""
        try:
            # Validate inputs
            validated_session_id = ChatValidators.validate_session_id(session_id)
            validated_account_id = ChatValidators.validate_account_id(account_id)
            
            logger.info(f"Finding or creating conversation for session_id: {validated_session_id}")
            
            # Try to find existing conversation
            conversation = ChatDBOperations.find_conversation_by_session(db, validated_session_id)
            
            if conversation:
                logger.info(f"Found existing conversation (ID: {conversation.id}) for session_id: {validated_session_id}")
                # Update account_id if provided and different
                if validated_account_id and conversation.account_id != validated_account_id:
                    ChatDBOperations.update_conversation_account(db, conversation, validated_account_id)
                return conversation
            
            # Create new conversation
            return ChatDBOperations.create_conversation(db, validated_session_id, validated_account_id)
            
        except ValidationError:
            logger.warning(f"Validation error in find_or_create_conversation: session_id={session_id}, account_id={account_id}")
            raise
        except ChatServiceError:
            raise
    
    @staticmethod
    def add_message(
        db: Session,
        conversation_id: UUID, 
        role: str, 
        content: str
    ) -> Message:
        """Add a message to a conversation."""
        try:
            # Validate inputs
            validated_role = ChatValidators.validate_message_role(role)
            validated_content = ChatValidators.validate_message_content(content, role)
            
            logger.info(f"Adding {role} message to conversation {conversation_id}")
            
            # Verify conversation exists
            if not ChatDBOperations.conversation_exists(db, conversation_id):
                raise ValidationError(f"Conversation with ID {conversation_id} not found")
            
            # Create message
            return ChatDBOperations.create_message(db, conversation_id, validated_role, validated_content)
            
        except ValidationError:
            logger.warning(f"Validation error in add_message: conversation_id={conversation_id}, role={role}")
            raise
        except ChatServiceError:
            raise
    
    @staticmethod
    def get_conversation_history(
        db: Session,
        session_id: UUID, 
        limit: int = DEFAULT_CONVERSATION_LIMIT
    ) -> List[ChatMessage]:
        """Retrieve conversation history for a session."""
        try:
            # Validate inputs
            validated_session_id = ChatValidators.validate_session_id(session_id)
            validated_limit = ChatValidators.validate_limit(limit)
            
            logger.info(f"Retrieving conversation history for session_id: {session_id}, limit: {limit}")
            
            # Find conversation
            conversation = ChatDBOperations.find_conversation_by_session(db, validated_session_id)
            
            if not conversation:
                logger.info(f"No conversation found for session_id: {session_id}")
                raise SessionNotFoundError(f"No conversation found for session: {session_id}")
            
            # Retrieve messages
            messages = ChatDBOperations.get_conversation_messages(db, conversation.id, validated_limit)
            
            # Convert to ChatMessage schema
            chat_messages = ChatDBOperations.messages_to_chat_messages(messages)
            
            logger.info(f"Retrieved {len(chat_messages)} messages for session {session_id}")
            return chat_messages
            
        except ValidationError:
            logger.warning(f"Validation error in get_conversation_history: session_id={session_id}, limit={limit}")
            raise
        except (SessionNotFoundError, ChatServiceError):
            raise
    
    @staticmethod
    def save_conversation_turn(
        db: Session,
        session_id: Optional[UUID], 
        account_id: Optional[str], 
        user_message: str, 
        assistant_response: str
    ) -> str:
        """Save a complete conversation turn (user message + assistant response)."""
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
            return conversation.session_id, assistant_msg.id
            
        except (ValidationError, ChatServiceError, SessionNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving conversation turn: {e}")
            db.rollback()
            raise ChatServiceError("Unexpected error occurred while saving conversation turn", e) from e