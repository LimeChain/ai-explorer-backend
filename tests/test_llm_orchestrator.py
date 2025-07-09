"""
Unit tests for the LLMOrchestrator service.
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.llm_orchestrator import LLMOrchestrator


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
            model="gpt-4o-mini",
            temperature=0.7,
            streaming=True,
        )
    
    @pytest.mark.asyncio
    async def test_stream_llm_response_success(self, mock_settings, mock_chat_openai):
        """Test successful streaming response from LLM."""
        # Setup mock response chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.content = "Hello"
        mock_chunk2 = MagicMock()
        mock_chunk2.content = " there"
        mock_chunk3 = MagicMock()
        mock_chunk3.content = "!"
        
        # Create an async generator for the mock
        async def mock_astream(messages):
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk
        
        # Create a mock LLM instance and set up the astream method
        mock_llm_instance = MagicMock()
        mock_llm_instance.astream = mock_astream
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test streaming response
        response_tokens = []
        async for token in orchestrator.stream_llm_response("Hello, AI!"):
            response_tokens.append(token)
        
        # Verify results
        assert response_tokens == ["Hello", " there", "!"]
        
        # Verify ChatOpenAI was called with correct parameters
        mock_chat_openai.assert_called_once_with(
            api_key=mock_settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0.7,
            streaming=True,
        )
    
    @pytest.mark.asyncio
    async def test_stream_llm_response_empty_content(self, mock_settings, mock_chat_openai):
        """Test handling of chunks with empty content."""
        # Setup mock response chunks with some empty content
        mock_chunk1 = MagicMock()
        mock_chunk1.content = "Hello"
        mock_chunk2 = MagicMock()
        mock_chunk2.content = ""  # Empty content
        mock_chunk3 = MagicMock()
        mock_chunk3.content = " world"
        
        # Create an async generator for the mock
        async def mock_astream(messages):
            for chunk in [mock_chunk1, mock_chunk2, mock_chunk3]:
                yield chunk
        
        # Create a mock LLM instance and set up the astream method
        mock_llm_instance = MagicMock()
        mock_llm_instance.astream = mock_astream
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test streaming response
        response_tokens = []
        async for token in orchestrator.stream_llm_response("test query"):
            response_tokens.append(token)
        
        # Verify that empty content is filtered out
        assert response_tokens == ["Hello", " world"]
    
    @pytest.mark.asyncio
    async def test_stream_llm_response_exception_handling(self, mock_settings, mock_chat_openai):
        """Test error handling when LLM service fails."""
        # Create a mock that raises an exception
        async def mock_astream_error(messages):
            raise Exception("API Error")
        
        mock_llm_instance = MagicMock()
        mock_llm_instance.astream = mock_astream_error
        mock_chat_openai.return_value = mock_llm_instance
        
        orchestrator = LLMOrchestrator()
        
        # Test error handling
        response_tokens = []
        async for token in orchestrator.stream_llm_response("test query"):
            response_tokens.append(token)
        
        # Verify error message is yielded
        assert len(response_tokens) == 1
        assert "Error: Unable to process your request" in response_tokens[0]