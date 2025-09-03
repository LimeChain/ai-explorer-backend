"""
LLM Orchestrator service implementing agentic workflow with LangGraph.
"""
import asyncio
from typing import AsyncGenerator, Callable, List, Optional, TypedDict
from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.messages import ChatMessage, HumanMessage, BaseMessage, AIMessage
from langchain_core.exceptions import LangChainException
from langgraph.graph import END
from langchain_mcp_adapters.tools import load_mcp_tools
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError
from app.prompts.system_prompts import AGENTIC_SYSTEM_PROMPT, RESPONSE_FORMATTING_SYSTEM_PROMPT
from app.services.chat_service import ChatService
from app.services.helpers.tool_call_parser import ToolCallParser
from app.services.helpers.workflow_builder import WorkflowBuilder
from app.services.helpers.response_streamer import ResponseStreamer
from app.services.helpers.message_converter import MessageConverter
from app.services.helpers.cost_calculator import CostCalculator
from app.services.helpers.constants import (
    MAX_QUERY_LENGTH, DEFAULT_TEMPERATURE
)
from app.utils.logging_config import get_service_logger

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = get_service_logger("llm_orchestrator", "api")



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
        self._graph_tasks = {}
        self.cost_calculator = CostCalculator()
        self.enable_persistence = enable_persistence
        logger.info("🤖 LLM Orchestrator initialized", extra={
            "agentic_workflow": True,
            "persistence_enabled": enable_persistence,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "temperature": DEFAULT_TEMPERATURE,
            "streaming": True
        })

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
    
    def _create_initial_state(self, query: Optional[str], account_id: Optional[str], session_id: UUID, db: Session, continue_from_message_id: Optional[UUID] = None) -> GraphState:
        """Create initial workflow state, loading conversation history from database."""
        messages = []
        
        if continue_from_message_id:
            # Continue from message case - load conversation history only
            logger.info("➡️ Continue from message %s requested for session %s", continue_from_message_id, session_id)
            try:
                chat_history = self.chat_service.get_conversation_history(db, session_id, continue_from_message_id=continue_from_message_id)
                if chat_history:
                    historical_messages = MessageConverter.chat_messages_to_langgraph_messages(chat_history)
                    messages.extend(historical_messages)
                    logger.info("📜 Loaded %s messages from database for continue from message %s", len(historical_messages), continue_from_message_id)
            except Exception as e:
                logger.warning("⚠️ Could not load conversation history for continue: %s", e)
        else:
            # Regular query - load conversation history and add new query
            try:
                chat_history = self.chat_service.get_conversation_history(db, session_id)
                if chat_history:
                    historical_messages = MessageConverter.chat_messages_to_langgraph_messages(chat_history)
                    messages.extend(historical_messages)
                    logger.info("📜 Loaded %s messages from database for session %s", len(historical_messages), session_id)
            except Exception as e:
                logger.warning("⚠️ Could not load conversation history for session %s: %s", session_id, e)
            
            # Add the new query as the latest message
            if query:
                messages.append(HumanMessage(content=query))
        
        return {
            "messages": messages,
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

    async def cancel_flow(self, session_id: UUID) -> None:
        """Cancel a running graph flow for a given session_id, if any."""
        if not session_id:
            return
        task = self._graph_tasks.get(session_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
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
                
                logger.info("💰 Cost calculation - Input: %d tokens ($%.6f), Output: %d tokens ($%.6f), Total: $%.6f", 
                           input_tokens, input_cost, output_tokens, output_cost, total_cost)
                
            except Exception as e:
                logger.error("❌ Error calculating token costs: %s", e)
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
            raise ImportError("Checkpointer not found: %s" % e)

    async def stream_llm_response(
        self, 
        query: Optional[str], 
        network: str,
        session_id: UUID,
        account_id: Optional[str] = None,
        db: Optional[Session] = None,
        continue_from_message_id: Optional[UUID] = None,
        on_complete: Optional[Callable[[UUID, UUID], None]] = None,
        on_cost_calculated: Optional[Callable[[GraphState], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response using agentic workflow with real token streaming."""
        try:
            import time
            start_time = time.time()
            
            if continue_from_message_id:
                logger.info("🔄 Starting LLM orchestration (continue mode)", extra={
                    "continue_from_message_id": str(continue_from_message_id),
                    "session_id": str(session_id),
                    "account_id": account_id,
                    "network": network
                })
            else:
                logger.info("🚀 Starting LLM orchestration (new query)", extra={
                    "session_id": str(session_id),
                    "account_id": "***" if account_id else None,
                    "network": network,
                    "query_length": len(query) if query else 0
                })
                self._validate_query(query)
            
            # Create checkpointer outside of MCP context to avoid connection conflicts
            checkpointer = self.get_checkpointer()
            logger.debug("Checkpointer initialized", extra={
                "persistence_enabled": self.enable_persistence,
                "checkpointer_available": checkpointer is not None
            })

            async with streamablehttp_client(settings.mcp_endpoint) as (read, write, _):
                async with ClientSession(read, write) as session:
                    session_start = time.time()
                    await session.initialize()
                    session_init_time = time.time() - session_start
                    
                    logger.info("MCP session initialized", extra={
                        "mcp_endpoint": settings.mcp_endpoint,
                        "initialization_time_ms": round(session_init_time * 1000, 2)
                    })

                    # Load tools and create workflow
                    tools_start = time.time()
                    tools = await load_mcp_tools(session)
                    tools_load_time = time.time() - tools_start
                    
                    logger.info("🛠️ MCP tools loaded", extra={
                        "tool_count": len(tools),
                        "tool_names": [tool.name for tool in tools] if tools else [],
                        "load_time_ms": round(tools_load_time * 1000, 2)
                    })

                    # Create node executors using helper classes
                    call_model_node = self.workflow_builder.create_model_node_executor(
                        self.llm, self._create_context_aware_system_prompt
                    )
                    call_tool_node = self.workflow_builder.create_tool_node_executor(tools, network)

                    # Build workflow
                    graph = self.workflow_builder.build_workflow(
                        GraphState, call_model_node, call_tool_node, self._continue_with_tool_or_end, checkpointer
                    )

                    config = {}

                    if checkpointer:
                        # Prepare config for memory persistence
                        config = {"configurable": {"thread_id": str(session_id)}}

                        # Check if session already exists
                        existing_state = await checkpointer.aget_tuple(config)
                        
                        if existing_state and existing_state.checkpoint:
                            # Get the actual workflow state from channel_values
                            channel_values = existing_state.checkpoint.get('channel_values', {})
                            if not channel_values or 'messages' not in channel_values:
                                logger.warning("⚠️ No messages found in existing state for session: %s, starting new session", session_id)
                                state = self._create_initial_state(query, account_id, session_id, db, continue_from_message_id)
                            else:
                                state = dict(channel_values)
                                logger.info("🔄 Resuming session", extra={"session_id": str(session_id), "msgs": len(state.get('messages', [])), "tools": len(state.get('tool_calls_made', [])), "flow": "continue"})
                                if query and not continue_from_message_id:  # Only add query if not continuing
                                    state["messages"].append(HumanMessage(content=query))
                        else:
                            # New session - create initial state with database history
                            logger.info("🆕 New session", extra={"session_id": str(session_id), "flow": "new"})
                            state = self._create_initial_state(query, account_id, session_id, db, continue_from_message_id)
                    else:
                        # No persistence - just run with initial state, still load database history
                        logger.info("🏃 Stateless session", extra={"session_id": str(session_id), "flow": "stateless"})
                        state = self._create_initial_state(query, account_id, session_id, db, continue_from_message_id)

                    logger.info("🤖 Executing agent workflow", extra={"session_id": str(session_id)})
                    final_state_task = asyncio.create_task(graph.ainvoke(state, config=config))
                    self._graph_tasks[session_id] = final_state_task

                    try:
                        final_state = await final_state_task
                        logger.info("✅ Agent workflow completed", extra={"session_id": str(session_id), "iterations": final_state.get('iteration_count', 0), "tools_used": len(final_state.get('tool_calls_made', []))})
                    finally:
                        self._graph_tasks.pop(session_id, None)

                    assistant_msg_id = None
                    user_msg_id = None
        
                    def on_complete_callback(_assistant_msg_id, _user_msg_id):

                        nonlocal assistant_msg_id
                        nonlocal user_msg_id
                        assistant_msg_id = _assistant_msg_id
                        user_msg_id = _user_msg_id

                    async for token in self.response_streamer.stream_final_response(
                        final_state,
                        RESPONSE_FORMATTING_SYSTEM_PROMPT,
                        query,
                        session_id,
                        account_id,
                        db,
                        is_continue=bool(continue_from_message_id),
                        on_complete=on_complete_callback
                    ):
                        yield token

                    final_state = await self._calculate_and_update_costs(final_state)
                    
                    if on_cost_calculated:
                        on_cost_calculated(final_state)

                    if on_complete and assistant_msg_id:
                        on_complete(assistant_msg_id, user_msg_id)

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error("❌ LangChain error during streaming: %s", e, exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error("❌ Unexpected error during LLM streaming: %s", e, exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e

