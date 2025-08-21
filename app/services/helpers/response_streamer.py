"""
Response streaming and persistence utilities.
"""
import logging
from uuid import UUID
from typing import AsyncGenerator, List, Optional, Tuple


from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

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
        messages: List[BaseMessage],
        response_system_prompt: str,
        query: Optional[str],
        session_id: UUID,
        account_id: Optional[str] = None,
        db: Optional[Session] = None,
        is_continue: bool = False,
        on_complete: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """Stream the final response and save to database."""
        # Prepare messages for final response
        final_messages = [SystemMessage(content=response_system_prompt)]
        query_text = query if query else "Continue conversation"
        final_messages.append(HumanMessage(content=f"User query: {query_text} \n\n Agent response: {messages[-1].content}"))

        accumulated_response = ""
        # Stream the response token by token
        async for chunk in self.llm.astream(final_messages):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                if isinstance(chunk.content, str):
                    accumulated_response += chunk.content
                    yield chunk.content
        
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
                    logger.info(f"Continue response saved (assistant only) for session: {session_id}")
                    return assistant_msg.id, None
                else:
                    # Normal flow - save both user message and assistant response
                    if not query:
                        logger.warning(f"No query provided for normal conversation flow")
                        return None, None
                    
                    saved_session_id, assistant_msg_id, user_msg_id = self.chat_service.save_conversation_turn(
                        session_id=session_id,
                        account_id=account_id,
                        user_message=query,
                        assistant_response=response,
                        db=db
                    )
                    logger.info(f"Conversation saved with session_id: {saved_session_id}")
                    return assistant_msg_id, user_msg_id
        except Exception as save_error:
            logger.error(f"Failed to save conversation: {save_error}")
            # Don't raise - shouldn't break streaming response