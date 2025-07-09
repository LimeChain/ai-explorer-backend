"""
LLM Orchestrator service for handling LLM interactions and streaming responses.
"""
import logging
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import LangChainException

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError


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
            model="gpt-4.1", # TODO: make this configurable
            temperature=0.7, # TODO: magic number, should be configurable
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
            LLMServiceError: If there's an error communicating with the LLM service
            ValidationError: If the input query is invalid
        """
        try:
            # Input validation
            if not query or not query.strip():
                raise ValidationError("Query cannot be empty or whitespace")
            if len(query) > 1000: # TODO: Adjust appropriate length limit and remove magic number
                raise ValidationError("Query exceeds maximum length of 1000 characters")
            
            logger.info(f"Processing query of length: {len(query)}")
            
            # Construct messages for the LLM
            messages = [
                SystemMessage(content="You are a helpful assistant for the THF AI Explorer, a blockchain explorer for the Hedera network. You help users understand blockchain data and transactions in simple, human-readable terms."),
                HumanMessage(content=query)
            ]
            
            # Stream the response
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    yield chunk.content
                    
        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except LangChainException as e:
            # Handle LangChain-specific exceptions
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            # Handle any other unexpected exceptions
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e