"""
Chat Service for managing conversation persistence.

This service handles GDPR-compliant storage of chat conversations for internal
analysis and AI agent improvement while maintaining user privacy.
"""
from uuid import UUID
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.db.models import Conversation, Message
from app.schemas.chat import ChatMessage
from app.exceptions import ChatServiceError, ValidationError, SessionNotFoundError
from app.services.helpers.chat_validators import ChatValidators
from app.services.helpers.chat_db_operations import ChatDBOperations
from app.services.helpers.constants import DEFAULT_CONVERSATION_LIMIT
from app.utils.logging_config import get_service_logger

logger = get_service_logger("chat", "api")


class ChatService:
    """Service for managing chat history persistence."""
    
    
    @staticmethod
    def find_or_create_conversation(
        db: Session,
        session_id: UUID, 
        account_id: Optional[str] = None
    ) -> Conversation:
        """Find existing conversation or create a new one."""
        try:
            # Validate inputs
            validated_session_id = ChatValidators.validate_session_id(session_id)
            validated_account_id = ChatValidators.validate_account_id(account_id)
            
            logger.info(
                "💬 Finding or creating conversation",
                extra={
                    "operation_type": "query",
                    "session_id": str(validated_session_id),
                    "account_id": validated_account_id
                }
            )
            
            # Try to find existing conversation
            conversation = ChatDBOperations.find_conversation_by_session(db, validated_session_id)
            
            if conversation:
                logger.info(
                    "✅ Found existing conversation",
                    extra={
                        "operation_type": "query",
                        "conversation_id": str(conversation.id),
                        "session_id": str(validated_session_id),
                        "message_count": len(conversation.messages)
                    }
                )
                # Update account_id if provided and different
                if validated_account_id and conversation.account_id != validated_account_id:
                    ChatDBOperations.update_conversation_account(db, conversation, validated_account_id)
                return conversation
            
            # Create new conversation
            logger.info(
                "✨ Creating new conversation",
                extra={
                    "operation_type": "create",
                    "session_id": str(validated_session_id),
                    "account_id": validated_account_id
                }
            )
            return ChatDBOperations.create_conversation(db, validated_session_id, validated_account_id)
            
        except ValidationError as e:
            logger.warning(
                "⚠️ Validation error in find_or_create_conversation",
                extra={
                    "operation_type": "validation",
                    "session_id": str(session_id),
                    "account_id": account_id,
                    "error": str(e)
                }
            )
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
            
            logger.info(
                "💬 Adding %s message", validated_role,
                extra={
                    "operation_type": "create",
                    "conversation_id": str(conversation_id),
                    "role": validated_role,
                    "content_length": len(validated_content)
                }
            )
            
            # Verify conversation exists
            if not ChatDBOperations.conversation_exists(db, conversation_id):
                raise ValidationError("Conversation with ID %s not found" % conversation_id)
            
            # Create message
            return ChatDBOperations.create_message(db, conversation_id, validated_role, validated_content)
            
        except ValidationError:
            logger.warning("Validation error in add_message: conversation_id=%s, role=%s", conversation_id, role)
            raise
        except ChatServiceError:
            raise
    
    @staticmethod
    def get_conversation_history(
        db: Session,
        session_id: UUID, 
        limit: int = DEFAULT_CONVERSATION_LIMIT,
        continue_from_message_id: Optional[UUID] = None
    ) -> List[ChatMessage]:
        """Retrieve conversation history for a session."""
        try:
            # Validate inputs
            validated_session_id = ChatValidators.validate_session_id(session_id)
            validated_limit = ChatValidators.validate_limit(limit)
            
            logger.info("Retrieving conversation history for session_id: %s, limit: %s", session_id, limit)
            
            # Find conversation
            conversation = ChatDBOperations.find_conversation_by_session(db, validated_session_id)
            
            if not conversation:
                logger.info("No conversation found for session_id: %s", session_id)
                raise SessionNotFoundError("No conversation found for session: %s" % session_id)

            if continue_from_message_id:
                pivot = ChatDBOperations.get_message_by_id(db, continue_from_message_id)
                if not pivot or pivot.conversation_id != conversation.id:
                    logger.warning("Message ID %s not found in conversation %s", continue_from_message_id, session_id)
                    raise ValidationError("Message ID %s not found in conversation %s" % (continue_from_message_id, session_id))
            
            # Retrieve messages
            messages = ChatDBOperations.get_conversation_messages(db, conversation.id, validated_limit, continue_from_message_id)
            
            # Convert to ChatMessage schema
            chat_messages = ChatDBOperations.messages_to_chat_messages(messages)
            
            logger.info("Retrieved %s messages for session %s", len(chat_messages), session_id)
            return chat_messages
            
        except ValidationError:
            logger.warning("Validation error in get_conversation_history: session_id=%s, limit=%s", session_id, limit)
            raise
        except (SessionNotFoundError, ChatServiceError):
            raise
    
    @staticmethod
    def save_conversation_turn(
        db: Session,
        session_id: UUID, 
        account_id: Optional[str], 
        user_message: str, 
        assistant_response: str
    ) -> Tuple[UUID, UUID, UUID]:
        """Save a complete conversation turn (user message + assistant response)."""
        try:
            logger.info("Saving conversation turn for session: %s", session_id)
            
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
            
            logger.info("Saved conversation turn (user: %s, assistant: %s) for session: %s", user_msg.id, assistant_msg.id, conversation.session_id)
            return conversation.session_id, assistant_msg.id, user_msg.id
            
        except (ValidationError, ChatServiceError, SessionNotFoundError):
            raise
        except Exception as e:
            logger.error("Unexpected error saving conversation turn: %s", e)
            db.rollback()
            raise ChatServiceError("Unexpected error occurred while saving conversation turn", e) from e
    
    @staticmethod
    def edit_message(
        db: Session,
        message_id: UUID,
        new_content: str
    ) -> Message:
        """Edit a user message and delete all subsequent messages."""
        try:
            logger.info("Editing message: %s", message_id)
            
            # Get the message to edit
            message = ChatDBOperations.get_message_by_id(db, message_id)
            if not message:
                raise ValidationError("Message with ID %s not found" % message_id)
            
            # Validate it's a user message
            if message.role != "user":
                raise ValidationError("Only user messages can be edited")
            
            # Validate content
            validated_content = ChatValidators.validate_message_content(new_content, "user")
            
            # Delete all messages created after this message's timestamp
            updated_message, deleted_count = ChatDBOperations.edit_message_and_delete_after(db, message_id, validated_content)
            
            logger.info("Edited message %s and deleted %s subsequent messages", message_id, deleted_count)
            return updated_message
            
        except ValidationError:
            raise
        except ChatServiceError:
            raise
        except Exception as e:
            logger.error("Unexpected error editing message: %s", e)
            db.rollback()
            raise ChatServiceError("Unexpected error occurred while editing message", e) from e
    

    @staticmethod 
    async def clear_session_checkpoint(session_id: UUID) -> None:
        """Clear checkpoint state for a session after message editing."""
        try:
            # Import checkpointer to avoid circular imports
            from app.main import checkpointer
            if checkpointer is None:
                logger.warning("Checkpointer not available, skipping checkpoint clear")
                return
            
            await checkpointer.adelete_thread(str(session_id))
            logger.info("Cleared checkpoint state for session %s", session_id)
            
        except Exception as e:
            # Don't fail the edit operation if checkpoint clearing fails
            logger.error("Failed to clear checkpoint for session %s: %s", session_id, e)
            # Don't raise - this is a best-effort operation