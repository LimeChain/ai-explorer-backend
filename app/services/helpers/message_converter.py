"""
Message format conversion utilities.

Converts between database ChatMessage objects and LangGraph BaseMessage objects.
"""
from typing import List
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from app.schemas.chat import ChatMessage


class MessageConverter:
    """Utility class for converting between message formats."""
    
    @staticmethod
    def chat_messages_to_langgraph_messages(chat_messages: List[ChatMessage]) -> List[BaseMessage]:
        """
        Convert ChatMessage objects to LangGraph BaseMessage objects.
        
        Args:
            chat_messages: List of ChatMessage objects from database
            
        Returns:
            List of BaseMessage objects for LangGraph
        """
        langgraph_messages = []
        
        for chat_msg in chat_messages:
            if chat_msg.role == "user":
                langgraph_messages.append(HumanMessage(content=chat_msg.content))
            elif chat_msg.role == "assistant":
                langgraph_messages.append(AIMessage(content=chat_msg.content))
            else:
                # Log warning but skip unknown roles
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️ Unknown message role: {chat_msg.role}, skipping message")
        
        return langgraph_messages