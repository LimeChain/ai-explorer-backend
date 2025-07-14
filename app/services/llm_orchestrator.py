"""
LLM Orchestrator service implementing agentic workflow with LangGraph.
"""
import logging
import json
from typing import AsyncGenerator, Dict, Any, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk, BaseMessage
from langchain_core.exceptions import LangChainException
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_mcp_adapters.tools import load_mcp_tools

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError
from app.prompts.system_prompts import AGENTIC_SYSTEM_PROMPT

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """
    State schema for the agentic workflow graph.
    
    This state tracks the conversation history and results of tool calls
    throughout the agent's execution.
    """
    messages: List[BaseMessage]  # Conversation history
    tool_calls_made: List[Dict[str, Any]]  # History of tool calls and results
    current_query: str  # The current user query being processed
    final_response: Optional[str]  # The final response to return to user
    iteration_count: int  # Track iterations to prevent infinite loops
    pending_tool_call: Optional[Dict[str, Any]]  # Tool call waiting to be executed


class LLMOrchestrator:
    """
    Agentic workflow orchestrator using LangGraph for stateful AI interactions.
    
    This class implements a stateful agent graph that handles LLM interactions
    and tool calls while preserving real token-by-token streaming.
    """
    
    def __init__(self):
        """Initialize the LLM Orchestrator with agentic workflow."""
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4.1-mini", # TODO: make this configurable
            temperature=0.1, # TODO: magic number, should be configurable
            streaming=True,
        )
        self.graph: Optional[CompiledStateGraph] = None
        self.mcp_session: Optional[ClientSession] = None
        self.tools: List[Any] = []
        logger.info("LLM Orchestrator initialized with agentic workflow")

    async def _call_model_node(self, state: GraphState) -> GraphState:
        """Graph node that calls the LLM model."""
        try:
            # Prepare messages for the model
            messages = [SystemMessage(content=AGENTIC_SYSTEM_PROMPT)]
            messages.extend(state["messages"])
            
            # Add tool call context if available
            if state["tool_calls_made"]:
                tool_context = "\\n\\nPrevious tool results:\\n" + "\\n".join([
                    f"Tool: {call['name']} -> Result: {call['result']}"
                    for call in state["tool_calls_made"][-3:]  # Last 3 tool calls
                ])
                messages.append(HumanMessage(content=tool_context))
            
            # Call the model (non-streaming for decision making)
            response = await self.llm.ainvoke(messages)
            
            # Update state with new message
            new_messages = state["messages"] + [response]
            state["messages"] = new_messages
            
            # Try to parse tool call from response
            print(f"LLM Response content: {response.content}")
            tool_call = self._parse_tool_call(response.content)
            print(f"Parsed tool call: {tool_call}")
            if tool_call:
                state["pending_tool_call"] = tool_call
                print("Setting pending_tool_call")
            else:
                state["final_response"] = response.content
                print("Setting final_response")
                
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            return state
            
        except Exception as e:
            logger.error(f"Error in call_model_node: {e}", exc_info=True)
            state["final_response"] = "I apologize, but I encountered an error. Please try again."
            return state

    def _should_continue(self, state: GraphState) -> str:
        """Determine graph routing based on state."""
        
        if state.get("iteration_count", 0) >= 7:
            if not state.get("final_response"):
                state["final_response"] = "I've reached the maximum number of steps. Please try rephrasing your question."
            return "end"
        
        if state.get("pending_tool_call"):
            return "continue"
        
        if state.get("final_response"):
            return "end"
        
        return "end"

    def _parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response expecting JSON format."""
        try:
            if not content or not content.strip():
                return None
            
            content = content.strip()
            
            # Look for JSON in code blocks
            if "```json" in content:
                start_idx = content.find("```json") + 7
                end_idx = content.find("```", start_idx)
                if end_idx != -1:
                    content = content[start_idx:end_idx].strip()
            # Look for JSON within the text
            elif "{" in content and "}" in content:
                start_idx = content.find("{")
                end_idx = content.rfind("}") + 1
                if start_idx != -1 and end_idx != 0:
                    json_candidate = content[start_idx:end_idx]
                    try:
                        parsed = json.loads(json_candidate)
                        if isinstance(parsed, dict) and "tool_call" in parsed:
                            tool_call = parsed["tool_call"]
                            if isinstance(tool_call, dict) and "name" in tool_call:
                                return tool_call
                    except json.JSONDecodeError:
                        pass
            
            # Try to parse the entire content as JSON
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "tool_call" in parsed:
                tool_call = parsed["tool_call"]
                if isinstance(tool_call, dict) and "name" in tool_call:
                    return tool_call
            
            return None
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    async def _call_tool_node_with_tools(self, state: GraphState, tools: List[Any]) -> GraphState:
        """Graph node that executes tool calls with provided tools."""
        try:
            tool_call = state.get("pending_tool_call")
            if not tool_call:
                state["final_response"] = "Error: No tool call found to execute."
                return state
            
            tool_name = tool_call["name"]
            tool_params = tool_call.get("parameters", {})
            
            # Find and execute the tool
            tool_to_call = None
            for tool in tools:
                if hasattr(tool, 'name') and tool.name == tool_name:
                    tool_to_call = tool
                    break
            
            if not tool_to_call:
                result = f"Error: Tool '{tool_name}' not found."
            else:
                # Special handling for call_sdk_method which expects method_name + **kwargs
                if tool_name == "call_sdk_method":
                    method_name = tool_params.get("method_name")
                    # Extract method_name and pass the rest as kwargs
                    kwargs = {k: v for k, v in tool_params.items() if k != "method_name"}
                    tool_input = {"method_name": method_name, "kwargs": kwargs}
                    result = await tool_to_call.ainvoke(tool_input)
                else:
                    result = await tool_to_call.ainvoke(tool_params)
            
            # Store the tool call result
            tool_call_record = {
                "name": tool_name,
                "parameters": tool_params,
                "result": result
            }
            
            state["tool_calls_made"] = state.get("tool_calls_made", []) + [tool_call_record]
            
            # Clear pending tool call and add result as message
            if "pending_tool_call" in state:
                del state["pending_tool_call"]
            
            tool_result_message = HumanMessage(
                content=f"Tool '{tool_name}' returned: {json.dumps(result, indent=2)}"
            )
            state["messages"] = state["messages"] + [tool_result_message]
            
            return state
            
        except Exception as e:
            logger.error(f"Error in call_tool_node_with_tools: {e}", exc_info=True)
            error_message = HumanMessage(content=f"Tool execution failed: {str(e)}")
            state["messages"] = state["messages"] + [error_message]
            return state

    async def stream_llm_response(self, query: str) -> AsyncGenerator[str, None]:
        """
        Stream LLM response using agentic workflow with real token streaming.
        
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
            if len(query) > 1000: # TODO: Adjust appropriate length limit
                raise ValidationError("Query exceeds maximum length of 1000 characters")
            
            # Use the original approach with proper MCP connection management
            async with streamablehttp_client('http://localhost:8001/mcp/') as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Load tools
                    tools = await load_mcp_tools(session)
                    logger.info(f"Loaded {len(tools)} tools")
                    
                    # Create workflow with tools in scope
                    workflow = StateGraph(GraphState)
                    
                    # Create node functions that capture tools in closure
                    async def call_model_node(state: GraphState) -> GraphState:
                        return await self._call_model_node(state)
                    
                    async def call_tool_node(state: GraphState) -> GraphState:
                        return await self._call_tool_node_with_tools(state, tools)
                    
                    # Add nodes
                    workflow.add_node("call_model", call_model_node)
                    workflow.add_node("call_tool", call_tool_node)
                    
                    # Add edges
                    workflow.set_entry_point("call_model")
                    workflow.add_conditional_edges(
                        "call_model",
                        self._should_continue,
                        {
                            "continue": "call_tool",
                            "end": END
                        }
                    )
                    workflow.add_edge("call_tool", "call_model")
                    
                    # Compile graph
                    graph = workflow.compile()
                    
                    # Initialize state and run workflow
                    initial_state: GraphState = {
                        "messages": [HumanMessage(content=query)],
                        "tool_calls_made": [],
                        "current_query": query,
                        "final_response": None,
                        "iteration_count": 0,
                        "pending_tool_call": None
                    }
                    
                    # Execute the agentic workflow
                    final_state = await graph.ainvoke(initial_state)
                    # Stream the final response
                    final_messages = final_state["messages"]
                    # Create streaming call with full conversation context
                    messages_for_streaming = [SystemMessage(content=AGENTIC_SYSTEM_PROMPT)]
                    messages_for_streaming.extend(final_messages)
                    messages_for_streaming.append(HumanMessage(content="Please provide a clear, final summary based on the tool results above."))
                    
                    # Stream the final response token by token
                    async for chunk in self.llm.astream(messages_for_streaming):
                        if isinstance(chunk, AIMessageChunk) and chunk.content:
                            if isinstance(chunk.content, str):
                                yield chunk.content

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e

    async def cleanup(self):
        """Cleanup resources."""
        if self.mcp_session:
            await self.mcp_session.close()
            self.mcp_session = None
