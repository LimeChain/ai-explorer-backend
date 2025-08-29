"""
Response streaming and persistence utilities.
"""
import logging
import tiktoken

from uuid import UUID

from typing import AsyncGenerator, Optional, TypedDict, Tuple


from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, AIMessageChunk, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from app.config import settings
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ResponseStreamer:
    """Handles streaming responses and conversation persistence."""
    
    def __init__(self, llm: BaseChatModel, chat_service: ChatService):
        self.llm = llm
        self.chat_service = chat_service
    
    async def stream_final_response(
        self,
        state: TypedDict,
        response_system_prompt: str,
        query: Optional[str],
        session_id: UUID,
        account_id: Optional[str] = None,
        db: Optional[Session] = None,
        is_continue: bool = False,
        on_complete: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """Stream the final response and save to database."""
        try:
            encoding = tiktoken.encoding_for_model(settings.llm_model)
        except Exception as e:
            # Fallback for unknown models/providers
            base = "o200k_base" if "gpt-4.1-mini" in settings.llm_model else "cl100k_base"
            logger.error(f"❌ Error getting encoding for model {settings.llm_model}: {e}")
            encoding = tiktoken.get_encoding(base)
            logger.warning(
                f"⚠️ Unknown model for tiktoken: provider={getattr(settings, 'llm_provider', 'unknown')}, "
                f"model={settings.llm_model}. Falling back to {base}."
            )
        
        # Prepare messages for final response
        final_messages = [SystemMessage(content=response_system_prompt)]
        query_text = query if query else "Continue conversation"
        final_messages.append(HumanMessage(content=f"User query: {query_text} \n\n Agent response: {state['messages'][-1].content}"))

        # Count input tokens
        try:
            input_tokens = len(encoding.encode(str(state['messages'][-1].content)))
        except Exception as e:
            logger.error("❌ Tokenization failed for input; approximating tokens", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "fallback_used": True,
                "operation": "input_tokenization"
            })
            input_tokens = max(1, len(str(state['messages'][-1].content)) // 4)


        accumulated_response = ""
        # Stream the response token by token
        async for chunk in self.llm.astream(final_messages):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                if isinstance(chunk.content, str):
                    accumulated_response += chunk.content
                    yield chunk.content
        
        # Count output tokens
        try:
            output_tokens = len(encoding.encode(accumulated_response))
        except Exception as e:
            logger.error("❌ Tokenization failed for output; approximating tokens", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "fallback_used": True,
                "operation": "output_tokenization",
                "response_length": len(accumulated_response)
            })
            output_tokens = max(1, len(accumulated_response) // 4)

        total_tokens = input_tokens + output_tokens
        
        state['total_input_tokens'] = state.get('total_input_tokens', 0) + input_tokens
        state['total_output_tokens'] = state.get('total_output_tokens', 0) + output_tokens
        
        logger.info(f"Response streaming tokens: {input_tokens} input + {output_tokens} output = {total_tokens} total")
        
        # Save conversation after streaming completes
        assistant_msg_id, user_msg_id = await self._save_conversation(
            session_id, account_id, query, accumulated_response.strip(), db, is_continue
        )

        if on_complete and assistant_msg_id:
            on_complete(assistant_msg_id, user_msg_id)
    
    async def _save_conversation(
        self, 
        session_id: UUID, 
        account_id: Optional[str], 
        query: Optional[str], 
        response: str,
        db: Optional[Session] = None,
        is_continue: bool = False
    ) -> Tuple[UUID, Optional[UUID]]:
        """Save conversation to database with error handling."""
        try:
            if response:
                if is_continue:
                    # For continue signals, only save the assistant response (no user message)
                    assistant_msg = self.chat_service.add_message(
                        db=db,
                        conversation_id=self.chat_service.find_or_create_conversation(
                            db, session_id, account_id
                        ).id,
                        role="assistant",
                        content=response
                    )
                    logger.info(f"💾 Continue response saved (assistant only) for session: {session_id}")
                    return assistant_msg.id, None
                else:
                    # Normal flow - save both user message and assistant response
                    saved_session_id, assistant_msg_id, user_msg_id = self.chat_service.save_conversation_turn(
                        session_id=session_id,
                        account_id=account_id,
                        user_message=query,
                        assistant_response=response,
                        db=db
                    )
                    logger.info(f"💾 Conversation saved with session_id: {saved_session_id}")
                    return assistant_msg_id, user_msg_id
        except Exception as save_error:
            logger.error(f"❌ Failed to save conversation: {save_error}")
            # Don't raise - shouldn't break streaming response