"""
LLM Orchestrator service for handling LLM interactions and streaming responses.
"""
import logging
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
from langchain_core.exceptions import LangChainException
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.tools import load_mcp_tools

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError
from app.prompts.system_prompts import CHAT_SYSTEM_PROMPT

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


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
            model="gpt-4.1-mini", # TODO: make this configurable
            temperature=0.1, # TODO: magic number, should be configurable
            streaming=True,
        )
        logger.info("LLM Orchestrator initialized with gpt-4o-mini model")


    async def stream_llm_response(self, query) -> AsyncGenerator[str, None]:
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
            if not query or not query.strip():
                raise ValidationError("Query cannot be empty or whitespace")
            if len(query) > 1000: # TODO: Adjust appropriate length limit and remove magic number
                raise ValidationError("Query exceeds maximum length of 1000 characters")
            
            async with streamablehttp_client('http://localhost:8001/mcp/') as (read, write, _): # TODO: make the mcp URL configurable, also note the usage of MultiServerMCPClient will be needed in future
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools = await load_mcp_tools(session)
                    logger.info(f"Loaded {len(tools)} tools")
                    
                    agent = create_react_agent(
                        self.llm, 
                        tools=tools,
                        prompt=CHAT_SYSTEM_PROMPT
                    )

                    async for chunk in agent.astream(
                        {"messages": [HumanMessage(content=query)]},
                        stream_mode='messages'
                    ):
                        if isinstance(chunk, tuple) and len(chunk) >= 2:
                            message = chunk[0]
                            if isinstance(message, AIMessageChunk) and message.content:
                                # Ensure we only yield strings
                                if isinstance(message.content, str):
                                    yield message.content

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e
