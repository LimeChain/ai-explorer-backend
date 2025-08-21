"""
Database models for the AI Explorer backend.
"""
import uuid
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as DBEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from .base import Base
from app.schemas.suggestions import SuggestionContext


class Conversation(Base):
    """
    Model for storing conversation sessions.
    
    This table stores anonymized conversation sessions with optional wallet address
    for personalized context while maintaining GDPR compliance.
    """
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), unique=True, index=True, nullable=False)
    account_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """
    Model for storing individual messages within conversations.
    
    This table stores both user queries and assistant responses with timestamps
    for internal analysis and AI agent improvement.
    """
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")


class SuggestedQuery(Base):
    """
    Model for storing suggested queries.
    
    This table stores pre-defined suggested queries that are shown to users
    based on their context (anonymous or connected wallet).
    """
    __tablename__ = 'suggested_queries'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(String, nullable=False)
    context = Column(DBEnum(SuggestionContext, name='suggestion_context_enum'), nullable=False, index=True)
    display_order = Column(Integer, default=0, nullable=False)  # For ordering suggestions in the UI

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FeedbackType(Enum):
    """
    Enum for feedback types.
    """
    POSITIVE = "positive"
    NEGATIVE = "negative"

class Feedback(Base):
    """
    Model for storing feedback.
    
    Each message can only have one feedback entry (enforced by unique constraint).
    """
    __tablename__ = 'feedback'
    __table_args__ = (
        UniqueConstraint('message_id', name='uq_feedback_message_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    feedback = Column(DBEnum(FeedbackType, name='feedback_type_enum'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())