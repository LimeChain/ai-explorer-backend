"""
Unit tests for the LLMOrchestrator service.
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_orchestrator import LLMOrchestrator
from app.exceptions import LLMServiceError, ValidationError


class TestLLMOrchestrator:
    """Test cases for LLMOrchestrator service."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('app.services.llm_orchestrator.settings') as mock_settings:
            mock_settings.openai_api_key = "test-api-key"
            yield mock_settings
    
    @pytest.fixture
    def mock_chat_openai(self):
        """Mock ChatOpenAI instance."""
        with patch('app.services.llm_orchestrator.ChatOpenAI') as mock_chat_openai:
            yield mock_chat_openai
    
    def test_llm_orchestrator_initialization(self, mock_settings, mock_chat_openai):
        """Test that LLMOrchestrator initializes correctly with proper parameters."""
        orchestrator = LLMOrchestrator()
        
        # Verify ChatOpenAI was called with correct parameters
        mock_chat_openai.assert_called_once_with(
            api_key="test-api-key",
            model="gpt-4.1-mini",
            temperature=0.1,
            streaming=True,
        )
    
    @pytest.mark.asyncio
    @patch('app.services.llm_orchestrator.streamablehttp_client')
    @patch('app.services.llm_orchestrator.ClientSession')
    @patch('app.services.llm_orchestrator.load_mcp_tools')
    @patch('app.services.llm_orchestrator.create_react_agent')
    async def test_stream_llm_response_success(self, mock_create_agent, mock_load_tools, 
                                             mock_client_session, mock_http_client,
                                             mock_settings, mock_chat_openai):
        """Test successful streaming response from LLM."""
        from langchain_core.messages import AIMessageChunk
        
        # Setup mock MCP components
        mock_session = MagicMock()
        mock_session.initialize = MagicMock()
        mock_client_session.return_value.__aenter__.return_value = mock_session
        
        mock_http_client.return_value.__aenter__.return_value = (None, None, None)
        
        mock_tools = [MagicMock()]
        mock_load_tools.return_value = mock_tools
        
        # Setup mock agent with streaming chunks
        mock_agent = MagicMock()
        
        # Create AIMessageChunk objects for proper streaming
        chunk1 = (AIMessageChunk(content="Hello"), {})
        chunk2 = (AIMessageChunk(content=" there"), {})
        chunk3 = (AIMessageChunk(content="!"), {})
        
        async def mock_astream(*args, **kwargs):
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk
        
        mock_agent.astream = mock_astream
        mock_create_agent.return_value = mock_agent
        
        # Create a mock LLM instance
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test streaming response
        response_tokens = []
        async for token in orchestrator.stream_llm_response("Hello, AI!"):
            response_tokens.append(token)
        
        # Verify results
        assert response_tokens == ["Hello", " there", "!"]
    
    @pytest.mark.asyncio
    @patch('app.services.llm_orchestrator.streamablehttp_client')
    @patch('app.services.llm_orchestrator.ClientSession')
    @patch('app.services.llm_orchestrator.load_mcp_tools')
    @patch('app.services.llm_orchestrator.create_react_agent')
    async def test_stream_llm_response_empty_content(self, mock_create_agent, mock_load_tools,
                                                   mock_client_session, mock_http_client,
                                                   mock_settings, mock_chat_openai):
        """Test handling of chunks with empty content."""
        from langchain_core.messages import AIMessageChunk
        
        # Setup mock MCP components
        mock_session = MagicMock()
        mock_session.initialize = MagicMock()
        mock_client_session.return_value.__aenter__.return_value = mock_session
        mock_http_client.return_value.__aenter__.return_value = (None, None, None)
        mock_load_tools.return_value = [MagicMock()]
        
        # Setup mock agent with chunks including empty content
        mock_agent = MagicMock()
        
        # Create AIMessageChunk objects including empty content
        chunk1 = (AIMessageChunk(content="Hello"), {})
        chunk2 = (AIMessageChunk(content=""), {})  # Empty content
        chunk3 = (AIMessageChunk(content=" world"), {})
        
        # Create an async generator for the mock
        async def mock_astream(*args, **kwargs):
            for chunk in [chunk1, chunk2, chunk3]:
                yield chunk
        
        mock_agent.astream = mock_astream
        mock_create_agent.return_value = mock_agent
        
        # Create a mock LLM instance
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test streaming response
        response_tokens = []
        async for token in orchestrator.stream_llm_response("test query"):
            response_tokens.append(token)
        
        # Verify that empty content is filtered out
        assert response_tokens == ["Hello", " world"]
    
    @pytest.mark.asyncio
    @patch('app.services.llm_orchestrator.streamablehttp_client')
    @patch('app.services.llm_orchestrator.ClientSession')
    @patch('app.services.llm_orchestrator.load_mcp_tools')
    @patch('app.services.llm_orchestrator.create_react_agent')
    async def test_stream_llm_response_exception_handling(self, mock_create_agent, mock_load_tools,
                                                        mock_client_session, mock_http_client,
                                                        mock_settings, mock_chat_openai):
        """Test error handling when LLM service fails."""
        # Setup mock MCP components
        mock_session = MagicMock()
        mock_session.initialize = MagicMock()
        mock_client_session.return_value.__aenter__.return_value = mock_session
        mock_http_client.return_value.__aenter__.return_value = (None, None, None)
        mock_load_tools.return_value = [MagicMock()]
        
        # Create a mock agent that raises an exception
        mock_agent = MagicMock()
        
        async def mock_astream_error(*args, **kwargs):
            raise Exception("API Error")
        
        mock_agent.astream = mock_astream_error
        mock_create_agent.return_value = mock_agent
        
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test error handling
        response_tokens = []
        async for token in orchestrator.stream_llm_response("test query"):
            response_tokens.append(token)
        
        # Verify error message is yielded
        assert len(response_tokens) == 1
        assert "Error: Unable to process your request" in response_tokens[0]
    
    @pytest.mark.asyncio
    async def test_validation_error_empty_query(self, mock_settings, mock_chat_openai):
        """Test that empty queries raise ValidationError."""
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test empty query
        with pytest.raises(ValidationError, match="Query cannot be empty or whitespace"):
            async for _ in orchestrator.stream_llm_response(""):
                pass
                
        # Test whitespace-only query
        with pytest.raises(ValidationError, match="Query cannot be empty or whitespace"):
            async for _ in orchestrator.stream_llm_response("   "):
                pass
    
    @pytest.mark.asyncio
    async def test_validation_error_long_query(self, mock_settings, mock_chat_openai):
        """Test that overly long queries raise ValidationError."""
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Create a query that exceeds the limit
        long_query = "a" * 1001
        
        with pytest.raises(ValidationError, match="Query exceeds maximum length"):
            async for _ in orchestrator.stream_llm_response(long_query):
                pass
    
    @pytest.mark.asyncio
    async def test_langchain_exception_handling(self, mock_settings, mock_chat_openai):
        """Test that LangChain exceptions are converted to LLMServiceError."""
        from langchain_core.exceptions import LangChainException
        
        # Create a mock that raises a LangChainException
        async def mock_astream_langchain_error(messages):
            raise LangChainException("API rate limit exceeded")
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.astream = mock_astream_langchain_error
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        with pytest.raises(LLMServiceError, match="The AI service encountered an unexpected error. Please try again in a moment."):
            async for _ in orchestrator.stream_llm_response("test query"):
                pass
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_handling(self, mock_settings, mock_chat_openai):
        """Test that unexpected exceptions are converted to LLMServiceError."""
        # Create a mock that raises an unexpected exception
        async def mock_astream_unexpected_error(messages):
            raise RuntimeError("Unexpected error")
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.astream = mock_astream_unexpected_error
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        with pytest.raises(LLMServiceError, match="The AI service encountered an unexpected error"):
            async for _ in orchestrator.stream_llm_response("test query"):
                pass