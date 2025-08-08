import logging

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.models import Feedback, FeedbackType, Message
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

class FeedbackRequest(BaseModel):
    feedback_type: FeedbackType

class FeedbackResponse(BaseModel):
    message: str
    feedback_id: UUID
    created_at: datetime

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
        
        # Check if feedback already exists for this message
        existing_feedback = db.query(Feedback).filter(Feedback.message_id == message_id).first()
        
        if existing_feedback:
            # Update existing feedback
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
            # Create new feedback
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
        
    except HTTPException:
        # Re-raise HTTPExceptions (like 404) without modification
        raise
    except IntegrityError as e:
        logger.error(f"Database integrity error while saving feedback: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid feedback data"
        )
    except Exception as e:
        logger.error(f"Unexpected error saving feedback: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback"
        )