"""
LLM Orchestrator service implementing agentic workflow with LangGraph.
"""
import logging
from typing import AsyncGenerator, Callable, List, Optional, TypedDict
from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
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
from app.services.helpers.cost_calculator import CostCalculator
from app.services.helpers.constants import (
    MAX_QUERY_LENGTH, DEFAULT_TEMPERATURE
)

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class GraphState(TypedDict):
    """State schema for the agentic workflow graph."""
    messages: List[BaseMessage]
    tool_calls_made: List[dict]
    iteration_count: int
    pending_tool_call: Optional[dict]
    account_id: Optional[str]
    total_input_tokens: Optional[int]
    total_output_tokens: Optional[int]
    total_input_cost: Optional[float]
    total_output_cost: Optional[float]
    total_cost: Optional[float]
    session_id: Optional[UUID]


class LLMOrchestrator:
    """Agentic workflow orchestrator using LangGraph for stateful AI interactions."""
    
    def __init__(self, enable_persistence: bool = True):
        """Initialize the LLM Orchestrator with agentic workflow.
        
        Args:
            enable_persistence: Whether to use checkpointer for state persistence.
                               Set to False for evaluations or testing.
        """
        self.llm = init_chat_model(
            model_provider=settings.llm_provider,
            model=settings.llm_model,
            temperature=DEFAULT_TEMPERATURE,
            streaming=True,
            api_key=settings.llm_api_key.get_secret_value(),
        )
        self.chat_service = ChatService()
        self.tool_parser = ToolCallParser()
        self.workflow_builder = WorkflowBuilder(self.tool_parser)
        self.response_streamer = ResponseStreamer(self.llm, self.chat_service)
        self.cost_calculator = CostCalculator()
        self.enable_persistence = enable_persistence
        logger.info(f"LLM Orchestrator initialized with agentic workflow (persistence: {enable_persistence})")

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
    
    def _create_initial_state(self, query: str, account_id: Optional[str], session_id: Optional[UUID]) -> GraphState:
        """Create initial workflow state."""
        return {
            "messages": [HumanMessage(content=query)],
            "tool_calls_made": [],
            "iteration_count": 0,
            "pending_tool_call": None,
            "account_id": account_id,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_input_cost": 0.0,
            "total_output_cost": 0.0,
            "total_cost": 0.0,
            "session_id": session_id
        }

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

    def _reset_cost_counters(self, state: GraphState) -> GraphState:
        """Reset all cost and token counters to zero."""
        state["total_input_tokens"] = 0
        state["total_output_tokens"] = 0
        state["total_input_cost"] = 0.0
        state["total_output_cost"] = 0.0
        state["total_cost"] = 0.0
        return state

    async def _calculate_and_update_costs(self, state: GraphState) -> GraphState:
        """Calculate token costs and update the state."""
        input_tokens = state.get("total_input_tokens", 0) or 0
        output_tokens = state.get("total_output_tokens", 0) or 0
        
        if input_tokens > 0 or output_tokens > 0:
            try:
                input_cost, output_cost, total_cost = self.cost_calculator.calculate_token_costs(
                    input_tokens, output_tokens
                )
                
                state["total_input_cost"] = input_cost
                state["total_output_cost"] = output_cost
                state["total_cost"] = total_cost
                
                logger.info(f"Cost calculation - Input: {input_tokens} tokens (${input_cost:.6f}), "
                           f"Output: {output_tokens} tokens (${output_cost:.6f}), "
                           f"Total: ${total_cost:.6f}")
                
            except Exception as e:
                logger.error(f"Error calculating token costs: {e}")
                # Set costs to 0 if calculation fails
                state["total_input_cost"] = 0.0
                state["total_output_cost"] = 0.0
                state["total_cost"] = 0.0
        
        return state

    def get_checkpointer(self):
        """Get checkpointer lazily to avoid circular import."""
        if not self.enable_persistence:
            return None
            
        try:
            from app.main import checkpointer
            if checkpointer is None:
                raise ImportError("Checkpointer not initialized. Ensure the application has started properly.")
            return checkpointer
        except ImportError as e :
            raise ImportError(f"Checkpointer not found: {e}")

    async def stream_llm_response(
        self, 
        query: str, 
        account_id: Optional[str] = None,
        session_id: Optional[UUID] = None,
        db: Optional[Session] = None,
        on_complete: Optional[Callable[[UUID], None]] = None,
        on_cost_calculated: Optional[Callable[[GraphState], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response using agentic workflow with real token streaming."""
        try:
            logger.info(f"Starting LLM orchestration for query: {query[:100]}...")
            self._validate_query(query)
            
            # Create checkpointer outside of MCP context to avoid connection conflicts
            checkpointer = self.get_checkpointer()

            async with streamablehttp_client(settings.mcp_endpoint) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized")

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
                        GraphState, call_model_node, call_tool_node, self._continue_with_tool_or_end, checkpointer
                    )
                    
                    if checkpointer:
                        # Prepare config for memory persistence
                        config = {
                            "configurable": {"thread_id": str(session_id)}
                        }

                        # Check if session already exists
                        existing_state = await checkpointer.aget_tuple(config)
                        
                        if existing_state and existing_state.checkpoint:
                            # Get the actual workflow state from channel_values
                            channel_values = existing_state.checkpoint.get('channel_values', {})
                            if not channel_values or 'messages' not in channel_values:
                                logger.warning(f"No messages found in existing state for session: {session_id}, starting new session")
                                initial_state = self._create_initial_state(query, account_id, session_id)
                                final_state = await graph.ainvoke(initial_state, config=config)
                            else:
                                restored_state = dict(channel_values)
                                logger.info(f"Resuming existing session: {session_id}")
                                logger.info(f"Existing state checkpoint ID: {existing_state.checkpoint.get('id', 'unknown')}")
                                restored_state["messages"].append(HumanMessage(content=query))
                                final_state = await graph.ainvoke(restored_state, config=config)
                        else:
                            # New session - create initial state
                            logger.info(f"Starting new session: {session_id}")
                            initial_state = self._create_initial_state(query, account_id, session_id)
                            final_state = await graph.ainvoke(initial_state, config=config)
                    else:
                        # No persistence - just run with initial state
                        logger.info(f"Running without persistence for session: {session_id}")
                        initial_state = self._create_initial_state(query, account_id, session_id)
                        final_state = await graph.ainvoke(initial_state)

                    assistant_msg_id = None
                    
                    def on_complete_callback(msg_id):
                        nonlocal assistant_msg_id
                        assistant_msg_id = msg_id

                    async for token in self.response_streamer.stream_final_response(
                        final_state,
                        RESPONSE_FORMATTING_SYSTEM_PROMPT,
                        query,
                        session_id,
                        account_id,
                        db,
                        on_complete=on_complete_callback
                    ):
                        yield token

                    final_state = await self._calculate_and_update_costs(final_state)
                    
                    if on_cost_calculated:
                        on_cost_calculated(final_state)

                    
                    self._reset_cost_counters(final_state)
                    if on_complete and assistant_msg_id:
                        on_complete(assistant_msg_id)

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e

