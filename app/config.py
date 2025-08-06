"""
Configuration settings for the AI Explorer backend service.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
from typing import List



class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        openai_api_key: OpenAI API key for LLM integration
        environment: Current environment (development, production, etc.)
        log_level: Logging level
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    openai_api_key: SecretStr = Field(default=SecretStr("your-api-key"), min_length=1, description="OpenAI API key (required)")
    embedding_model: str = Field(default="text-embedding-3-small", description="The model to use for embeddings")
    chat_model: str = Field(default="gpt-4.1-mini", description="The model to use")

    environment: str = Field(default="development", pattern="^(development|production|staging)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    mcp_endpoint: str = Field(default="http://mcp-server:8001/mcp/", description="MCP server endpoint")
    allowed_origins: List[str] = Field(
        default=["*"],
        description="List of allowed CORS origins"
    )

    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_project: str = Field(default="ai-explorer-backend", description="LangSmith project name")
    langsmith_api_key: SecretStr = Field(default=SecretStr("your-api-key"), min_length=1, description="LangSmith API key (required)")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")

    def model_post_init(self, __context: None) -> None:
        """Initialize LangSmith environment variables after settings are loaded."""

        if self.langsmith_tracing:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_ENDPOINT"] = self.langsmith_endpoint
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key.get_secret_value()
            os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project
        else:
            os.environ.pop("LANGCHAIN_TRACING_V2", None)
            os.environ.pop("LANGCHAIN_ENDPOINT", None)
            os.environ.pop("LANGCHAIN_API_KEY", None)
            os.environ.pop("LANGCHAIN_PROJECT", None)
    # Database settings
    database_url: str = Field(
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=5, description="Database connection pool max overflow")
    database_pool_timeout: int = Field(default=30, description="Database connection pool timeout in seconds")
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")

    # Vector store settings
    collection_name: str = Field(default="sdk_methods", description="Vector store collection name")

# Global settings instance
settings = Settings()