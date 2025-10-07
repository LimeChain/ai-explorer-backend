"""Configuration settings for the AI Agent MCP Server."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API connection settings
    api_base_url: str = Field(
        default="ws://localhost:8000",
        description="Base URL for the AI Explorer API"
    )
    
    # MCP server settings (hardcoded)
    server_name: str = "ai-explorer-mcp-external"
    server_version: str = "0.1.0"
    
    # Timeout settings
    websocket_timeout: int = Field(
        default=300,  # 5 minutes
        description="WebSocket connection timeout in seconds"
    )
    
    request_timeout: int = Field(
        default=120,  # 2 minutes
        description="Request timeout in seconds"
    )
    
    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # HTTP server settings
    http_host: str = Field(
        default="0.0.0.0",
        description="HTTP server host"
    )
    
    http_port: int = Field(
        default=8002,
        description="HTTP server port"
    )
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"  # Ignore extra environment variables
    }


# Global settings instance
settings = Settings()