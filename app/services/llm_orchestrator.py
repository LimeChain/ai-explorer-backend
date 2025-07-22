"""
LLM Orchestrator service implementing agentic workflow with LangGraph.
"""
import logging
import json
import os
from typing import AsyncGenerator, Dict, Any, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk, BaseMessage
from langchain_core.exceptions import LangChainException
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_mcp_adapters.tools import load_mcp_tools
from langsmith import traceable

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import LLMServiceError, ValidationError, ChatServiceError
from app.prompts.system_prompts import AGENTIC_SYSTEM_PROMPT
from app.schemas.chat import ChatMessage
from app.services.chat_service import ChatService

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client



logger = logging.getLogger(__name__)

# Constants
MAX_QUERY_LENGTH = 1000
MAX_ITERATIONS = 12
MAX_TOOL_CONTEXT_ITEMS = 10
DEFAULT_TEMPERATURE = 0.1


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
    account_id: Optional[str]  # Connected wallet address for personalized context


class LLMOrchestrator:
    """
    Agentic workflow orchestrator using LangGraph for stateful AI interactions.
    
    This class implements a stateful agent graph that handles LLM interactions
    and tool calls while preserving real token-by-token streaming.
    """
    
    def __init__(self):
        """Initialize the LLM Orchestrator with agentic workflow."""

        if settings.langsmith_tracing:
            logger.info("LangSmith tracing enabled")
        else:
            logger.info("LangSmith tracing disabled")
        
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.chat_model,
            temperature=DEFAULT_TEMPERATURE,
            streaming=True,
        )
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

    async def _call_model_node(self, state: GraphState) -> GraphState:
        """Graph node that calls the LLM model."""
        try:
            # Prepare messages for the model with context-aware system prompt
            system_prompt = self._create_context_aware_system_prompt(state.get("account_id"))
            messages = [SystemMessage(content=system_prompt)]
            messages.extend(state["messages"])
            
            # Add tool call context if available
            if state["tool_calls_made"]:
                tool_context = "\\n\\nPrevious tool results:\\n" + "\\n".join([
                    f"Tool: {call['name']} -> Result: {call['result']}"
                    for call in state["tool_calls_made"][-MAX_TOOL_CONTEXT_ITEMS:]
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
            print('tools to be added to pending_tool_calls: ', tool_call)
            print(f"Parsed tool call: {tool_call}")
            
            if tool_call:
                state["pending_tool_call"] = tool_call
                print("Setting pending_tool_call")
            else:
                # Check if this is a continuation vs final response
                is_final = self._is_response_final(response.content)
                logger.debug(f"Response analysis: is_final={is_final}, content_length={len(response.content)}")
                if is_final:
                    state["final_response"] = response.content
                    print("Setting final_response - detected conclusive response")
                    logger.info(f"Final response set at iteration {state.get('iteration_count', 0)}")
                else:
                    print("Detected partial response - continuing workflow without final_response")
                    logger.info(f"Partial response detected at iteration {state.get('iteration_count', 0)} - workflow will continue")
                
            state["iteration_count"] = state.get("iteration_count", 0) + 1
            return state
            
        except Exception as e:
            logger.error(f"Error in call_model_node: {e}", exc_info=True)
            state["final_response"] = "I apologize, but I encountered an error. Please try again."
            return state

    def _is_response_final(self, content: str) -> bool:
        """
        Determine if a response is final or if the workflow should continue.
        
        Args:
            content: The LLM response content
            
        Returns:
            True if this is a final response, False if it should continue
        """
        if not content:
            return True
            
        content_lower = content.lower().strip()
        
        # Strong continuation signals - definitely not final
        continuation_phrases = [
            "i will continue", "let me continue", "continuing with", "for the remaining",
            "next, i'll", "i'll also", "additionally", "furthermore", "i need to",
            "let me also", "i should also", "i'll now", "proceeding with",
            "i will now", "let me now", "i'll fetch", "i need to fetch",
            "i should fetch", "let me get", "i'll get", "i will get"
        ]
        
        # Check for explicit continuation signals
        if any(phrase in content_lower for phrase in continuation_phrases):
            logger.debug(f"Found continuation phrase in response")
            return False
            
        # Check for incomplete lists or partial data
        incomplete_indicators = [
            "...", "more", "additional", "rest of", "remaining", 
            "partial", "incomplete", "in progress", "continuing"
        ]
        
        if any(indicator in content_lower for indicator in incomplete_indicators):
            return False
            
        # Check for questions asking to continue
        continuation_questions = [
            "would you like me to", "shall i", "should i continue", 
            "do you want", "need me to", "want me to continue"
        ]
        
        if any(question in content_lower for question in continuation_questions):
            return True  # This is actually final - asking for user input
            
        # Strong conclusive signals - definitely final
        conclusive_phrases = [
            "that completes", "that's all", "this completes", "finished",
            "done", "complete", "summary", "in conclusion", "to summarize",
            "final result", "total", "overall", "that's the"
        ]
        
        if any(phrase in content_lower for phrase in conclusive_phrases):
            return True
            
        # If none of the above, check the structure
        # If it's a short response (< 100 chars), likely final
        if len(content) < 100:
            return True
            
        # If it ends with a question mark, it's asking user for input - final
        if content_lower.endswith('?'):
            return True
            
        # Default to continuing if uncertain - better to over-continue than under-continue
        return False

    def _should_continue(self, state: GraphState) -> str:
        """Determine graph routing based on state with improved decision logic."""
        
        iteration_count = state.get("iteration_count", 0)
        print('final response: ', state.get("final_response"))
        print('pending tool calls: ', state.get('pending_tool_call'))
        # Check for natural conclusion first (LLM provided final response without tool call)
        if state.get("final_response") and not state.get("pending_tool_call"):
            logger.info(f"Natural conclusion reached at iteration {iteration_count}")
            return "end"
        
        # Check for maximum iterations
        if iteration_count >= MAX_ITERATIONS:
            if not state.get("final_response"):
                # Use the last AI message as the final response instead of generic message
                ai_messages = [msg for msg in state.get("messages", []) 
                             if hasattr(msg, 'content') and hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__]
                if ai_messages and ai_messages[-1].content:
                    state["final_response"] = ai_messages[-1].content
                    logger.info(f"Using last AI response as final result after {iteration_count} iterations")
                else:
                    # Check if we have any useful tool results to summarize
                    tool_calls = state.get("tool_calls_made", [])
                    if tool_calls:
                        state["final_response"] = f"I've completed {len(tool_calls)} data retrievals. While I reached my iteration limit, I was able to gather the requested information. Please let me know if you need clarification on any specific details."
                        logger.info(f"Generated summary response after {iteration_count} iterations with {len(tool_calls)} tool calls")
                    else:
                        state["final_response"] = "I've reached the maximum number of steps without being able to complete your request. Please try rephrasing your question with more specific details."
                        logger.warning(f"Reached max iterations without meaningful progress")
            else:
                logger.info(f"Max iterations reached but final response already set")
            return "end"
        
        # Continue if there's a pending tool call
        if state.get("pending_tool_call"):
            logger.debug(f"Continuing workflow - pending tool call at iteration {iteration_count}")
            return "continue"
        
        # Check for excessive tool calls without progress (circular behavior detection)
        tool_calls = state.get("tool_calls_made", [])
        if len(tool_calls) > 8:  # If more than 8 tool calls, check for repetitive patterns
            recent_tools = [call.get("name") for call in tool_calls[-4:]]
            if len(set(recent_tools)) == 1:  # Same tool called 4 times in a row
                state["final_response"] = "I notice I'm repeating the same operation. Let me provide what I've found so far."
                logger.warning(f"Detected repetitive tool usage pattern: {recent_tools}")
                return "end"
        
        # Enhanced natural termination detection
        if not state.get("final_response"):
            # Check the last AI message to see if it indicates continuation
            messages = state.get("messages", [])
            last_ai_message = None
            
            for msg in reversed(messages):
                if hasattr(msg, 'content') and hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__:
                    last_ai_message = msg
                    break
            
            if last_ai_message and last_ai_message.content:
                # If the last message suggests continuation but has no tool call, continue anyway
                if not self._is_response_final(last_ai_message.content):
                    logger.debug(f"Continuing - last AI message suggests more work needed")
                    return "continue"
                else:
                    # Natural final response - use it
                    state["final_response"] = last_ai_message.content
                    logger.debug(f"Using last AI message as final response")
                    return "end"
        
        # Default to end (natural conclusion with explicit final_response)
        logger.debug(f"Ending workflow - no pending actions at iteration {iteration_count}")
        return "end"

    def _extract_json_from_codeblock(self, content: str) -> Optional[str]:
        """Extract JSON from ```json code blocks."""
        if "```json" not in content:
            return None
        
        start_idx = content.find("```json") + 7
        end_idx = content.find("```", start_idx)
        if end_idx == -1:
            return None
        
        return content[start_idx:end_idx].strip()

    def _extract_json_from_braces(self, content: str) -> Optional[str]:
        """Extract JSON from first { to last } in content."""
        if "{" not in content or "}" not in content:
            return None
        
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            return None
        
        return content[start_idx:end_idx]
    
    def _extract_json_from_tool_call_marker(self, content: str) -> Optional[str]:
        """Extract JSON by looking for 'tool_call' keyword as a marker."""
        if "tool_call" not in content.lower():
            return None
            
        # Find the first brace after "tool_call"
        tool_call_idx = content.lower().find("tool_call")
        search_start = max(0, tool_call_idx - 50)  # Look a bit before tool_call
        
        # Find the opening brace
        start_idx = content.find("{", search_start)
        if start_idx == -1:
            return None
            
        # Find the matching closing brace
        brace_count = 0
        end_idx = start_idx
        for i in range(start_idx, len(content)):
            if content[i] == "{":
                brace_count += 1
            elif content[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if brace_count != 0:  # Unmatched braces
            return None
            
        return content[start_idx:end_idx]
    
    def _extract_json_from_last_brace_pair(self, content: str) -> Optional[str]:
        """Extract JSON from the last complete brace pair in content."""
        if "{" not in content or "}" not in content:
            return None
            
        # Find all opening braces and try the last one
        brace_positions = [i for i, c in enumerate(content) if c == "{"]
        
        for start_idx in reversed(brace_positions):
            # Find the matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            
            if brace_count == 0:  # Found complete pair
                candidate = content[start_idx:end_idx]
                # Quick validation - should contain "tool_call"
                if "tool_call" in candidate.lower():
                    return candidate
                    
        return None

    def _validate_tool_call(self, parsed_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and extract tool call from parsed JSON."""
        if not isinstance(parsed_json, dict) or "tool_call" not in parsed_json:
            return None
        
        tool_call = parsed_json["tool_call"]
        if not isinstance(tool_call, dict) or "name" not in tool_call:
            return None
        
        return tool_call

    def _parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response, handling mixed content and JSON."""
        if not content or not content.strip():
            return None
        
        content = content.strip()
        
        # Enhanced extraction strategies that handle mixed content better
        extraction_strategies = [
            self._extract_json_from_codeblock,           # ```json ... ```
            self._extract_json_from_braces,              # { ... }
            self._extract_json_from_tool_call_marker,    # Look for "tool_call" markers
            self._extract_json_from_last_brace_pair,     # Last complete brace pair
            lambda c: c  # Try parsing the entire content as fallback
        ]
        
        for strategy in extraction_strategies:
            json_candidate = strategy(content)
            if json_candidate:
                try:
                    parsed = json.loads(json_candidate)
                    tool_call = self._validate_tool_call(parsed)
                    if tool_call:
                        return tool_call
                except json.JSONDecodeError:
                    continue
        
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
                logger.warning(f"Tool '{tool_name}' not found in available tools")
            else:
                logger.info(f"Executing tool '{tool_name}' with parameters: {tool_params}")
                try:
                    # Special handling for call_sdk_method which expects method_name + **kwargs
                    if tool_name == "call_sdk_method":
                        method_name = tool_params.get("method_name")
                        # Extract method_name and pass the rest as kwargs
                        kwargs = {k: v for k, v in tool_params.items() if k != "method_name"}
                        tool_input = {"method_name": method_name, "kwargs": kwargs}
                        result = await tool_to_call.ainvoke(tool_input)
                    else:
                        result = await tool_to_call.ainvoke(tool_params)
                    logger.info(f"Tool '{tool_name}' executed successfully")
                except Exception as tool_error:
                    logger.info(f"Tool '{tool_name}' execution failed: {tool_error}")
                    result = f"Error executing tool '{tool_name}': {str(tool_error)}"
            
            # Store the tool call result
            tool_call_record = {
                "name": tool_name,
                "parameters": tool_params,
                "result": result
            }

            print('result: ', tool_call_record)
            
            state["tool_calls_made"] = state.get("tool_calls_made", []) + [tool_call_record]
            
            # Clear pending tool call
            state.pop("pending_tool_call", None)
            
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


    async def stream_llm_response(
        self, 
        query: str, 
        account_id: Optional[str] = None,
        conversation_history: Optional[List[ChatMessage]] = None,
        session_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response using agentic workflow with real token streaming.
        
        Args:
            query: The user's natural language query
            account_id: Optional connected wallet address for personalized context
            conversation_history: Optional list of previous conversation messages
            session_id: Optional session identifier for conversation persistence
            db: Optional database session for conversation persistence
            
        Yields:
            str: Individual tokens from the LLM response
            
        Raises:
            LLMServiceError: If there's an error communicating with the LLM service
            ValidationError: If the input query is invalid
        """
        try:
            if not query or not query.strip():
                raise ValidationError("Query cannot be empty or whitespace")
            if len(query) > MAX_QUERY_LENGTH:
                raise ValidationError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
            
            # Use the original approach with proper MCP connection management
            async with streamablehttp_client(settings.mcp_endpoint) as (read, write, _):
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
                    
                    # Build initial messages from conversation history
                    initial_messages = []
                    if conversation_history:
                        # Convert ChatMessage objects to LangChain messages
                        for msg in conversation_history:
                            if msg.role == "user":
                                initial_messages.append(HumanMessage(content=msg.content))
                            elif msg.role == "assistant":
                                initial_messages.append(AIMessage(content=msg.content))
                    else:
                        # If no conversation history, just use the current query
                        initial_messages = [HumanMessage(content=query)]
                    
                    # Initialize state and run workflow
                    initial_state: GraphState = {
                        "messages": initial_messages,
                        "tool_calls_made": [],
                        "current_query": query,
                        "final_response": None,
                        "iteration_count": 0,
                        "pending_tool_call": None,
                        "account_id": account_id
                    }
                    
                    # Execute the agentic workflow
                    final_state = await graph.ainvoke(initial_state)
                    
                    # Check if we have a pre-computed final response (from improved _should_continue logic)
                    if final_state.get("final_response"):
                        # Stream the pre-computed final response directly
                        accumulated_response = final_state["final_response"]
                        
                        # Stream it word by word to simulate streaming
                        import asyncio
                        words = accumulated_response.split()
                        for i, word in enumerate(words):
                            if i == 0:
                                yield word
                            else:
                                yield " " + word
                            await asyncio.sleep(0.01)  # Small delay to simulate natural streaming
                    else:
                        # Fallback: Stream fresh response using LLM (should rarely happen now)
                        final_messages = final_state["messages"]
                        context_system_prompt = self._create_context_aware_system_prompt(account_id)
                        messages_for_streaming = [SystemMessage(content=context_system_prompt)]
                        messages_for_streaming.extend(final_messages)
                        
                        accumulated_response = ""
                        
                        async for chunk in self.llm.astream(messages_for_streaming):
                            if isinstance(chunk, AIMessageChunk) and chunk.content:
                                if isinstance(chunk.content, str):
                                    accumulated_response += chunk.content
                                    yield chunk.content
                    
                    # Save the conversation to database after streaming is complete
                    if db and accumulated_response.strip():  # Only save if we have a db session and response
                        try:
                            saved_session_id = ChatService.save_conversation_turn(
                                db=db,
                                session_id=session_id,
                                account_id=account_id,
                                user_message=query,
                                assistant_response=accumulated_response.strip()
                            )
                            logger.info(f"Conversation saved with session_id: {saved_session_id}")
                        except (ChatServiceError, ValidationError) as save_error:
                            logger.error(f"Failed to save conversation: {save_error}")
                            # Don't raise the error as it shouldn't break the streaming response
                        except Exception as save_error:
                            logger.error(f"Unexpected error saving conversation: {save_error}")
                            # Don't raise the error as it shouldn't break the streaming response

        except ValidationError:
            raise
        except LangChainException as e:
            logger.error(f"LangChain error during streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service is currently unavailable. Please try again in a moment.") from e
        except Exception as e:
            logger.error(f"Unexpected error during LLM streaming: {e}", exc_info=True)
            raise LLMServiceError("The AI service encountered an unexpected error. Please try again in a moment.") from e

