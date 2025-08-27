import logging

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.models import Feedback, FeedbackType, Message
from app.db.session import get_db
from app.services.chat_service import ChatService
from app.exceptions import ValidationError, ChatServiceError

logger = logging.getLogger(__name__)
router = APIRouter()

class FeedbackRequest(BaseModel):
    feedback_type: FeedbackType

class FeedbackResponse(BaseModel):
    message: str
    feedback_id: UUID
    created_at: datetime

class MessageEditRequest(BaseModel):
    content: str
    generate_response: bool = False

class MessageEditResponse(BaseModel):
    message: str
    message_id: UUID
    session_id: UUID
    conversation_id: UUID
    deleted_count: int
    edited_at: datetime

@router.post("/message/{message_id}/feedback", response_model=FeedbackResponse)
def feedback(
    message_id: UUID, 
    feedback_request: FeedbackRequest, 
    db: Session = Depends(get_db)
):
    """
    Submit or update feedback for a specific message.
    
    If feedback already exists, it will be updated. If not, a new feedback will be created.
    
    Args:
        message_id: UUID of the message to provide feedback for
        feedback_request: Feedback data including type and optional comment
        
    Returns:
        FeedbackResponse with confirmation and feedback details
    """
    try:
        # Validate message exists
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Message with ID {message_id} not found"
            )
        
        # Try to create new feedback (will fail if duplicate due to unique constraint)
        try:
            feedback = Feedback(
                message_id=message_id,
                feedback=feedback_request.feedback_type
            )
            
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            
            logger.info(
                f"Feedback created successfully",
                extra={
                    "feedback_id": str(feedback.id),
                    "message_id": str(message_id),
                    "feedback_type": feedback_request.feedback_type.value,
                    "action": "created"
                }
            )
            
            return FeedbackResponse(
                message="Feedback received successfully",
                feedback_id=feedback.id,
                created_at=feedback.created_at,
            )
            
        except IntegrityError as e:
            # Handle unique constraint violation - feedback already exists
            db.rollback()
            
            # Check if it's our unique constraint violation
            if "uq_feedback_message_id" in str(e):
                # Update existing feedback instead
                existing_feedback = db.query(Feedback).filter(Feedback.message_id == message_id).first()
                if existing_feedback:
                    existing_feedback.feedback = feedback_request.feedback_type
                    
                    db.commit()
                    db.refresh(existing_feedback)
                    
                    logger.info(
                        f"Feedback updated successfully",
                        extra={
                            "feedback_id": str(existing_feedback.id),
                            "message_id": str(message_id),
                            "feedback_type": feedback_request.feedback_type.value,
                            "action": "updated"
                        }
                    )
                    
                    return FeedbackResponse(
                        message="Feedback updated successfully",
                        feedback_id=existing_feedback.id,
                        created_at=existing_feedback.created_at,
                    )
                else:
                    # This shouldn't happen but handle gracefully
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Feedback constraint violation but no existing feedback found"
                    )
            else:
                # Re-raise if it's a different integrity error
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid feedback data"
                )
        
    except HTTPException:
        # Re-raise HTTPExceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving feedback: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback"
        )

@router.put("/message/{message_id}/edit", response_model=MessageEditResponse)
async def edit_message(
    message_id: UUID, 
    edit_request: MessageEditRequest, 
    db: Session = Depends(get_db)
):
    """
    Edit a user message and delete all subsequent messages.
    
    Args:
        message_id: UUID of the message to edit
        edit_request: New content for the message
        
    Returns:
        MessageEditResponse with confirmation and edit details
    """
    try:
        # Validate message exists and is a user message
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Message with ID {message_id} not found"
            )
        
        # Get count of messages that will be deleted for response
        messages_after = db.query(Message).filter(
            Message.conversation_id == message.conversation_id,
            Message.created_at > message.created_at
        ).count()
        
        # Edit the message using ChatService
        updated_message = ChatService.edit_message(
            db=db,
            message_id=message_id,
            new_content=edit_request.content
        )
        
        # Clear checkpoint state for the session (best-effort, don't fail if it errors)
        conversation = db.query(Message).filter(Message.id == message_id).first().conversation
        if conversation:
            await ChatService.clear_session_checkpoint(conversation.session_id)
        
        logger.info(
            f"Message edited successfully",
            extra={
                "message_id": str(message_id),
                "deleted_count": messages_after,
                "conversation_id": str(message.conversation_id),
                "session_id": str(conversation.session_id)
            }
        )
        
        return MessageEditResponse(
            message="Message edited successfully",
            message_id=updated_message.id,
            session_id=conversation.session_id,
            conversation_id=updated_message.conversation_id,
            deleted_count=messages_after,
            edited_at=updated_message.edited_at
        )
        
    except ValidationError as e:
        logger.warning(f"Validation error editing message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ChatServiceError as e:
        logger.error(f"Service error editing message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to edit message"
        )
    except Exception as e:
        logger.error(f"Unexpected error editing message {message_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to edit message"
        )