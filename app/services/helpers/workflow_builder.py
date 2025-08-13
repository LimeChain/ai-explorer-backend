"""
LangGraph workflow building utilities.
"""
import json
import logging
from typing import Dict, Any, List, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages.utils import (
    trim_messages,
    count_tokens_approximately
)
from langgraph.checkpoint.base import Checkpoint
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

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
        checkpointer: Checkpoint
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
        
        return workflow.compile(checkpointer=checkpointer)
    
    def create_model_node_executor(
        self, 
        llm, 
        system_prompt_func: Callable,
        max_tool_context_items: int = MAX_TOOL_CONTEXT_ITEMS
    ):
        """Create a model node execution function with proper context handling."""
        async def call_model_node(state):
            try:
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
                # Call the model
                response = await llm.ainvoke(messages, {"recursion_limit": RECURSION_LIMIT})
                
                # Update state with new message
                state["messages"] = state["messages"] + [response]
                
                # Parse tool call from response
                logger.info(f"LLM Response content: {response.content}")
                tool_call = self.tool_parser.parse_tool_call(response.content)
                logger.info(f"Parsed tool call: {tool_call}")
                
                if tool_call:
                    state["pending_tool_call"] = tool_call
                    logger.info("Setting pending_tool_call")
                else:
                    state["final_response"] = response.content
                    logger.info("Setting final_response")
                
                state["iteration_count"] = state.get("iteration_count", 0) + 1
                return state
                
            except Exception as e:
                logger.error(f"Error in call_model_node: {e}", exc_info=True)
                state["final_response"] = "I apologize, but I encountered an error. Please try again."
                return state
        
        return call_model_node
    
    def create_tool_node_executor(self, tools: List[Any]):
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
                result = await self._execute_tool(tools, tool_name, tool_params)
                
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
                logger.error(f"Error in call_tool_node: {e}", exc_info=True)
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
    
    async def _execute_tool(self, tools: List[Any], tool_name: str, tool_params: Dict) -> Any:
        """Execute a specific tool with given parameters."""
        # Find the tool
        tool_to_call = None
        for tool in tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                tool_to_call = tool
                break
        
        if not tool_to_call:
            error_msg = f"Error: Tool '{tool_name}' not found."
            logger.warning(f"Tool '{tool_name}' not found in available tools")
            return error_msg
        
        logger.info(f"Executing tool '{tool_name}' with parameters: {tool_params}")
        
        try:
            # Special handling for call_sdk_method
            if tool_name == ToolName.CALL_SDK_METHOD:
                method_name = tool_params.get("method_name")
                kwargs = {k: v for k, v in tool_params.items() if k != "method_name"}
                tool_input = {"method_name": method_name, "kwargs": kwargs}
                result = await tool_to_call.ainvoke(tool_input)
            else:
                result = await tool_to_call.ainvoke(tool_params)
            
            logger.info(f"Tool '{tool_name}' executed successfully")
            return result
            
        except Exception as tool_error:
            logger.error(f"Tool '{tool_name}' execution failed: {tool_error}")
            return f"Error executing tool '{tool_name}': {str(tool_error)}"