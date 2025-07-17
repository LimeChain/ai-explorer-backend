"""
Database models for the AI Explorer backend.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Conversation(Base):
    """
    Model for storing conversation sessions.
    
    This table stores anonymized conversation sessions with optional wallet address
    for personalized context while maintaining GDPR compliance.
    """
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
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
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")