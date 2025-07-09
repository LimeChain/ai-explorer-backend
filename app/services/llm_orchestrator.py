"""
LLM Orchestrator service for handling LLM interactions and streaming responses.
"""
import logging
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings


logger = logging.getLogger(__name__)


class LLMOrchestrator:
    """
    Service for orchestrating LLM interactions with streaming capabilities.
    
    This class manages communication with OpenAI's LLM using LangChain,
    providing token-by-token streaming responses for better user experience.
    """
    
    def __init__(self):
        """Initialize the LLM Orchestrator with OpenAI configuration."""
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0.7,
            streaming=True,
        )
        logger.info("LLM Orchestrator initialized with gpt-4o-mini model")
    
    async def stream_llm_response(self, query: str) -> AsyncGenerator[str, None]:
        """
        Stream LLM response token by token for a given user query.
        
        This method constructs a conversation with a system prompt and user query,
        then streams the response from the LLM token by token using LangChain's
        async streaming capabilities.
        
        Args:
            query: The user's natural language query
            
        Yields:
            str: Individual tokens from the LLM response
            
        Raises:
            Exception: If there's an error communicating with the LLM service
        """
        try:
            logger.info(f"Processing query: {query}")
            
            # Construct messages for the LLM
            messages = [
                SystemMessage(content="You are a helpful assistant for the THF AI Explorer, a blockchain explorer for the Hedera network. You help users understand blockchain data and transactions in simple, human-readable terms."),
                HumanMessage(content=query)
            ]
            
            # Stream the response
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            yield f"Error: Unable to process your request. Please try again."