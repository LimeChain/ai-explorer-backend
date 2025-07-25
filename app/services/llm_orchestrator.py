"""
LLM Orchestrator service implementing agentic workflow with LangGraph.
"""
import logging
from typing import AsyncGenerator, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.exceptions import LangChainException
from langgraph.graph import END
from langchain_mcp_adapters.tools import load_mcp_tools
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError
from app.prompts.system_prompts import AGENTIC_SYSTEM_PROMPT, RESPONSE_FORMATTING_SYSTEM_PROMPT
from app.schemas.chat import ChatMessage
from app.services.chat_service import ChatService
from app.services.helpers.tool_call_parser import ToolCallParser
from app.services.helpers.workflow_builder import WorkflowBuilder
from app.services.helpers.response_streamer import ResponseStreamer
from app.services.helpers.constants import (
    MAX_QUERY_LENGTH, DEFAULT_TEMPERATURE, RECURSION_LIMIT
)

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class GraphState(TypedDict):
    """State schema for the agentic workflow graph."""
    messages: List[BaseMessage]
    tool_calls_made: List[dict]
    current_query: str
    final_response: Optional[str]
    iteration_count: int
    pending_tool_call: Optional[dict]
    account_id: Optional[str]


class LLMOrchestrator:
    """Agentic workflow orchestrator using LangGraph for stateful AI interactions."""
    
    def __init__(self):
        """Initialize the LLM Orchestrator with agentic workflow."""
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.chat_model,
            temperature=DEFAULT_TEMPERATURE,
            streaming=True,
        )
        self.chat_service = ChatService()
        self.tool_parser = ToolCallParser()
        self.workflow_builder = WorkflowBuilder(self.tool_parser)
        self.response_streamer = ResponseStreamer(self.llm, self.chat_service)
        logger.info("LLM Orchestrator initialized with agentic workflow")

    def _create_context_aware_system_prompt(self, account_id: Optional[str]) -> str:
        """Create a context-aware system prompt that includes account information."""
        base_prompt = AGENTIC_SYSTEM_PROMPT
        
        if account_id:
            context_addition = f"""
            USER CONTEXT:
            The user is connected with wallet address {account_id}. Use this address as the context for any relevant questions about 'my' account, 'my' transactions, 'my' balance, or similar personal queries. When the user asks about 'my' anything related to blockchain data, they are referring to this specific account: {account_id}.

            Examples:
            - "What is my wallet address?" -> "Your wallet address is {account_id}."
            - "Show me my transactions" -> Query transactions for account {account_id}
            - "What is my balance?" -> Check balance for account {account_id}
            """
            return base_prompt + context_addition
        
        return base_prompt


    def _continue_with_tool_or_end(self, state: GraphState) -> str:
        """Determine graph routing based on state."""
        if state.get("pending_tool_call"):
            return "call_tool"
        return END


    def _validate_query(self, query: str) -> None:
        """Validate input query."""
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty or whitespace")
        if len(query) > MAX_QUERY_LENGTH:
            raise ValidationError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
    
    def _build_initial_messages(self, query: str, conversation_history: Optional[List[ChatMessage]]) -> List[BaseMessage]:
        """Build initial messages from conversation history."""
        if conversation_history:
            messages = []
            for msg in conversation_history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
            return messages
        return [HumanMessage(content=query)]
    
    def _create_initial_state(self, messages: List[BaseMessage], query: str, account_id: Optional[str]) -> GraphState:
        """Create initial workflow state."""
        return {
            "messages": messages,
            "tool_calls_made": [],
            "current_query": query,
            "final_response": None,
            "iteration_count": 0,
            "pending_tool_call": None,
            "account_id": account_id
        }

    async def stream_llm_response(
        self, 
        query: str, 
        account_id: Optional[str] = None,
        conversation_history: Optional[List[ChatMessage]] = None,
        session_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response using agentic workflow with real token streaming."""
        try:
            logger.info(f"Starting LLM orchestration for query: {query[:100]}...")
            self._validate_query(query)
            
            async with streamablehttp_client(settings.mcp_endpoint) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized")
                    print('MCP session initialized')
                    
                    # Load tools and create workflow
                    tools = await load_mcp_tools(session)
                    logger.info(f"Loaded {len(tools)} tools")
                    
                    # Create node executors using helper classes
                    call_model_node = self.workflow_builder.create_model_node_executor(
                        self.llm, self._create_context_aware_system_prompt
                    )
                    call_tool_node = self.workflow_builder.create_tool_node_executor(tools)
                    
                    # Build workflow
                    graph = self.workflow_builder.build_workflow(
                        GraphState, call_model_node, call_tool_node, self._continue_with_tool_or_end
                    )
                    
                    # Prepare initial state
                    initial_messages = self._build_initial_messages(query, conversation_history)
                    initial_state = self._create_initial_state(initial_messages, query, account_id)
                    
                    # Execute workflow
                    final_state = await graph.ainvoke(initial_state, {"recursion_limit": RECURSION_LIMIT})
                    
                    # Stream final response
                    async for token in self.response_streamer.stream_final_response(
                        final_state["messages"],
                        RESPONSE_FORMATTING_SYSTEM_PROMPT,
                        query,
                        session_id,
                        account_id,
                        db
                    ):
                        yield token

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e

