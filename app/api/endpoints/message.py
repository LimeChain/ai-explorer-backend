from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.models import Feedback, FeedbackType, Message
from app.db.session import get_async_db
from app.services.chat_service import ChatService
from app.exceptions import ValidationError, ChatServiceError
from app.utils.logging_config import get_api_logger

logger = get_api_logger("message")
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
async def feedback(
    message_id: UUID,
    feedback_request: FeedbackRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Submit or update feedback for a specific message.

    If feedback already exists, it will be updated. If not, a new feedback will be created.
    """
    import time
    request_start = time.time()

    try:
        # Validate message exists
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with ID {message_id} not found"
            )

        # Try to create new feedback (will fail if duplicate due to unique constraint)
        try:
            new_feedback = Feedback(
                message_id=message_id,
                feedback=feedback_request.feedback_type
            )

            db.add(new_feedback)
            await db.commit()
            await db.refresh(new_feedback)

            response_time = round((time.time() - request_start) * 1000, 2)
            logger.info("Feedback created successfully", extra={
                "message_id": str(message_id),
                "feedback_id": str(new_feedback.id),
                "feedback_type": feedback_request.feedback_type.value,
                "action": "created",
                "response_time_ms": response_time
            })

            return FeedbackResponse(
                message="Feedback received successfully",
                feedback_id=new_feedback.id,
                created_at=new_feedback.created_at,
            )

        except IntegrityError as e:
            # Handle unique constraint violation - feedback already exists
            await db.rollback()

            # Check if it's our unique constraint violation
            if "uq_feedback_message_id" in str(e):
                # Update existing feedback instead
                result = await db.execute(
                    select(Feedback).where(Feedback.message_id == message_id)
                )
                existing_feedback = result.scalar_one_or_none()
                if existing_feedback:
                    existing_feedback.feedback = feedback_request.feedback_type

                    await db.commit()
                    await db.refresh(existing_feedback)

                    response_time = round((time.time() - request_start) * 1000, 2)
                    logger.info("Feedback updated successfully", extra={
                        "message_id": str(message_id),
                        "feedback_id": str(existing_feedback.id),
                        "feedback_type": feedback_request.feedback_type.value,
                        "action": "updated",
                        "response_time_ms": response_time
                    })

                    return FeedbackResponse(
                        message="Feedback updated successfully",
                        feedback_id=existing_feedback.id,
                        created_at=existing_feedback.created_at,
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Feedback constraint violation but no existing feedback found"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid feedback data"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error saving feedback: %s", e, exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback"
        )

@router.put("/message/{message_id}/edit", response_model=MessageEditResponse)
async def edit_message(
    message_id: UUID,
    edit_request: MessageEditRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Edit a user message and delete all subsequent messages.
    """
    import time
    request_start = time.time()

    content_preview = edit_request.content[:50] + "..." if len(edit_request.content) > 50 else edit_request.content
    logger.info("Message edit API access", extra={
        "endpoint": "PUT /message/{message_id}/edit",
        "message_id": str(message_id),
        "content_preview": content_preview,
        "generate_response": edit_request.generate_response,
        "request_timestamp": time.time()
    })

    try:
        # Validate message exists
        result = await db.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with ID {message_id} not found"
            )

        # Count messages that will be deleted
        from sqlalchemy import func
        count_result = await db.execute(
            select(func.count()).select_from(Message).where(
                Message.conversation_id == message.conversation_id,
                Message.created_at > message.created_at
            )
        )
        messages_after = count_result.scalar()

        # Edit the message using ChatService (sync bridge — ChatService migrated in Story 1-2)
        updated_message = await db.run_sync(
            lambda sync_session: ChatService.edit_message(
                db=sync_session,
                message_id=message_id,
                new_content=edit_request.content
            )
        )

        # Clear checkpoint state for the session
        # Re-fetch the message to get conversation relationship
        conversation = None
        result = await db.execute(
            select(Message).where(Message.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg:
            # Load conversation via run_sync for relationship access
            conversation = await db.run_sync(
                lambda sync_session: sync_session.get(Message, message_id).conversation
            )
            if conversation:
                await ChatService.clear_session_checkpoint(conversation.session_id)

        response_time = round((time.time() - request_start) * 1000, 2)
        logger.info("Message edited successfully", extra={
            "message_id": str(message_id),
            "deleted_count": messages_after,
            "response_time_ms": response_time
        })

        return MessageEditResponse(
            message="Message edited successfully",
            message_id=updated_message.id,
            session_id=conversation.session_id if conversation else None,
            conversation_id=updated_message.conversation_id,
            deleted_count=messages_after,
            edited_at=updated_message.edited_at
        )

    except ValidationError as e:
        logger.warning("Validation error editing message %s: %s", message_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ChatServiceError as e:
        logger.error("Service error editing message %s: %s", message_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to edit message"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error editing message %s: %s", message_id, e, exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to edit message"
        )
