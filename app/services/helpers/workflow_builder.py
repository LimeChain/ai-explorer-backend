"""
LangGraph workflow building utilities.
"""
import json
import logging
import tiktoken

from typing import Dict, Any, List, Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.utils import trim_messages
from langgraph.checkpoint.base import Checkpoint
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.settings import settings
from app.services.helpers.tool_call_parser import ToolCallParser
from app.services.helpers.constants import MAX_TOOL_CONTEXT_ITEMS, RECURSION_LIMIT, ToolName, MAX_CHAT_HISTORY_MESSAGES

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WorkflowBuilder:
    """Builds and manages LangGraph workflows for the agentic system."""
    
    def __init__(self, tool_parser: ToolCallParser):
        self.tool_parser = tool_parser
    
    def build_workflow(
        self,
        graph_state_class,
        call_model_func: Callable,
        call_tool_func: Callable,
        continue_condition_func: Callable,
        checkpointer: Optional[Checkpoint]
    ) -> CompiledStateGraph:
        """Build a complete LangGraph workflow."""     
        workflow = StateGraph(graph_state_class)
        
        # Add nodes
        workflow.add_node("call_model", call_model_func)
        workflow.add_node("call_tool", call_tool_func)
        
        # Add edges
        workflow.set_entry_point("call_model")
        workflow.add_conditional_edges("call_model", continue_condition_func)
        workflow.add_edge("call_tool", "call_model")
        
        # Compile with or without checkpointer
        if checkpointer:
            return workflow.compile(checkpointer=checkpointer)
        else:
            return workflow.compile()
    
    def create_model_node_executor(
        self, 
        llm, 
        system_prompt_func: Callable,
        max_tool_context_items: int = MAX_TOOL_CONTEXT_ITEMS
    ):
        """Create a model node execution function with proper context handling."""
        async def call_model_node(state):
            try:
                try:
                    encoding = tiktoken.encoding_for_model(settings.llm_model)
                except Exception:
                    # Fallback for unknown models/providers
                    base = "o200k_base" if "gpt-4.1-mini" in settings.llm_model else "cl100k_base"
                    encoding = tiktoken.get_encoding(base)
                    logger.debug(
                        "Using %s encoding for non-OpenAI model: %s (provider: %s)",
                        base, settings.llm_model, getattr(settings, 'llm_provider', 'unknown')
                    )
                
                # Prepare messages with context-aware system prompt
                system_prompt = system_prompt_func(state.get("account_id"))
                messages = [SystemMessage(content=system_prompt)]
                messages.extend(state["messages"])

                messages = trim_messages(
                    messages,
                    strategy="last",
                    token_counter=len,
                    max_tokens=MAX_CHAT_HISTORY_MESSAGES,
                    start_on='human',
                    end_on=('human', 'tool'),
                    include_system=True
                )
                
                # Add tool call context if available
                if state["tool_calls_made"]:
                    tool_context = self._build_tool_context(
                        state["tool_calls_made"], 
                        max_tool_context_items
                    )
                    messages.append(HumanMessage(content=tool_context))
                # Count input tokens
                input_tokens = sum(len(encoding.encode(str(msg.content))) for msg in messages)
                
                # Call the model
                response = await llm.ainvoke(messages, {"recursion_limit": RECURSION_LIMIT})
                
                # Count output tokens
                output_tokens = len(encoding.encode(str(response.content)))
                total_tokens = input_tokens + output_tokens
                
                logger.info("Model call tokens: %d input + %d output = %d total", input_tokens, output_tokens, total_tokens)
                state["total_input_tokens"] = state.get("total_input_tokens", 0) + input_tokens
                state["total_output_tokens"] = state.get("total_output_tokens", 0) + output_tokens
                # Update state with new message
                state["messages"] = state["messages"] + [response]
                
                # Parse tool call from response
                tool_call = self.tool_parser.parse_tool_call(response.content)
                
                if tool_call:
                    state["pending_tool_call"] = tool_call
                    logger.debug("🔍 Parsed tool call: %s", tool_call['name'])
                else:
                    state["final_response"] = response.content
                    logger.debug("✅ Generated final response")
                
                state["iteration_count"] = state.get("iteration_count", 0) + 1
                return state
                
            except Exception as e:
                logger.error("❌ Error in call_model_node: %s", e, exc_info=True)
                state["final_response"] = "I apologize, but I encountered an error. Please try again."
                return state
        
        return call_model_node
    
    def create_tool_node_executor(self, tools: List[Any], network: str):
        """Create a tool node execution function with proper error handling."""
        async def call_tool_node(state):
            try:
                tool_call = state.get("pending_tool_call")
                if not tool_call:
                    state["final_response"] = "Error: No tool call found to execute."
                    return state
                
                tool_name = tool_call["name"]
                tool_params = tool_call.get("parameters", {})
                
                # Find and execute the tool
                result = await self._execute_tool(tools, tool_name, tool_params, network)
                
                logger.info("✅ %s completed", tool_name, extra={"result_size": len(str(result)) if result else 0})
                
                # Store the tool call result
                tool_call_record = {
                    "name": tool_name,
                    "parameters": tool_params,
                    "result": result
                }
                
                state["tool_calls_made"] = state.get("tool_calls_made", []) + [tool_call_record]
                state['pending_tool_call'] = None
                
                # Add tool result to messages
                tool_result_message = HumanMessage(
                    content=f"Tool '{tool_name}' returned: {json.dumps(result, indent=2)}"
                )
                state["messages"] = state["messages"] + [tool_result_message]
                
                return state
                
            except Exception as e:
                logger.error("❌ Error in call_tool_node: %s", e, exc_info=True)
                error_message = HumanMessage(content=f"Tool execution failed: {str(e)}")
                state["messages"] = state["messages"] + [error_message]
                return state
        
        return call_tool_node
    
    def _build_tool_context(self, tool_calls_made: List[Dict], max_items: int) -> str:
        """Build tool context string from previous tool calls."""
        recent_tools = tool_calls_made[-max_items:]
        tool_summaries = [
            f"Tool: {call['name']} -> Result: {call['result']}"
            for call in recent_tools
        ]
        return "\n\nPrevious tool results:\n" + "\n".join(tool_summaries)
    
    async def _execute_tool(self, tools: List[Any], tool_name: str, tool_params: Dict, network: str) -> Any:
        """Execute a specific tool with given parameters."""
        # Find the tool
        tool_to_call = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                tool_to_call = tool
                break
        
        if not tool_to_call:
            error_msg = "Error: Tool '%s' not found." % tool_name
            logger.warning("⚠️ Tool '%s' not found in available tools", tool_name)
            return error_msg
        
        try:
            # Special handling for call_sdk_method
            if tool_name == ToolName.CALL_SDK_METHOD:
                method_name = tool_params.get("method_name")
                kwargs = {k: v for k, v in tool_params.items() if k != "method_name"}
                tool_input = {"method_name": method_name, "kwargs": kwargs, "network": network}
                result = await tool_to_call.ainvoke(tool_input)
            elif tool_name == ToolName.CALCULATE_HBAR_VALUE:
                effective_params = (
                    {"network": network, **tool_params}
                    if "network" not in tool_params
                    else dict(tool_params)
                )
                result = await tool_to_call.ainvoke(effective_params)
            else:
                result = await tool_to_call.ainvoke(tool_params)
            
            logger.info("⚙️ Tool '%s' with parameters: %s executed successfully", tool_name, tool_params)
            return result
            
        except Exception as tool_error:
            logger.error("❌ Tool '%s' execution failed: %s", tool_name, tool_error)
            return "Error executing tool '%s': %s" % (tool_name, str(tool_error))