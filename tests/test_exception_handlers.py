"""
Integration tests for global exception handlers.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.exceptions import LLMServiceError, ValidationError


class TestExceptionHandlers:
    """Test cases for global exception handlers."""
    
    def test_llm_service_error_handler(self):
        """Test that LLMServiceError is converted to HTTP 503."""
        client = TestClient(app)
        
        # Mock the LLMOrchestrator to raise LLMServiceError
        with patch('app.api.endpoints.chat.llm_orchestrator') as mock_orchestrator:
            mock_orchestrator.stream_llm_response.side_effect = LLMServiceError(
                "The AI service is currently unavailable. Please try again in a moment."
            )
            
            response = client.post(
                "/api/v1/chat/",
                json={"query": "test query"}
            )
            assert response.status_code == 503
            assert response.headers["content-type"] == "application/json"
            
            error_data = response.json()
            assert "detail" in error_data
            assert "AI service is currently unavailable" in error_data["detail"]
    
    def test_validation_error_handler(self):
        """Test that ValidationError is converted to HTTP 400."""
        client = TestClient(app)
        
        # Mock the LLMOrchestrator to raise ValidationError
        with patch('app.api.endpoints.chat.llm_orchestrator') as mock_orchestrator:
            mock_orchestrator.stream_llm_response.side_effect = ValidationError(
                "Query cannot be empty or whitespace"
            )
            
            response = client.post(
                "/api/v1/chat/",
                json={"query": ""}
            )
            
            assert response.status_code == 422
            assert response.headers["content-type"] == "application/json"
            
            error_data = response.json()
            assert "detail" in error_data
            assert "String should have at least 1 character" in error_data["detail"][0]["msg"]
    
    def test_successful_request_not_affected(self):
        """Test that successful requests are not affected by exception handlers."""
        client = TestClient(app)
        
        # Mock the LLMOrchestrator to return successful response
        async def mock_stream_response(query):
            yield "Hello"
            yield " world"
        
        with patch('app.api.endpoints.chat.llm_orchestrator') as mock_orchestrator:
            mock_orchestrator.stream_llm_response = mock_stream_response
            
            response = client.post(
                "/api/v1/chat/",
                json={"query": "test query"}
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # Check that response contains expected streaming data
            content = response.content.decode()
            assert "data: Hello" in content
            assert "data:  world" in content
    
    def test_pydantic_validation_error(self):
        """Test that Pydantic validation errors return 422."""
        client = TestClient(app)
        
        # Send invalid JSON (missing required field)
        response = client.post(
            "/api/v1/chat/",
            json={}  # Missing 'query' field
        )
        
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/json"
        
        error_data = response.json()
        assert "detail" in error_data
        # Pydantic validation error should mention the missing field
        assert any("query" in str(error).lower() for error in error_data["detail"])
    
    def test_invalid_json_format(self):
        """Test that invalid JSON format returns 422."""
        client = TestClient(app)
        
        # Send malformed JSON
        response = client.post(
            "/api/v1/chat/",
            data="invalid json",
            headers={"content-type": "application/json"}
        )
        
        assert response.status_code == 422