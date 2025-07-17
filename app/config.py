"""
Configuration settings for the AI Explorer backend service.
"""
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
    environment: str = Field(default="development", pattern="^(development|production|staging)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    mcp_endpoint: str = Field(default="http://mcp-server:7001/mcp/", description="MCP server endpoint")
    chat_model: str = Field(default="gpt-4.1-mini", description="The model to use")
    allowed_origins: List[str] = Field(
        default=["*"],
        description="List of allowed CORS origins"
    )

    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_project: str = Field(default="ai-explorer-backend", description="LangSmith project name")
    langsmith_api_key: SecretStr = Field(default=SecretStr("your-api-key"), min_length=1, description="LangSmith API key (required)")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith API endpoint")

    # Database settings
    database_url: str = Field(
        default="postgresql://ai_explorer:ai_explorer@localhost:5432/ai_explorer", 
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=0, description="Database connection pool max overflow")
    database_pool_timeout: int = Field(default=30, description="Database connection pool timeout in seconds")
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")


# Global settings instance
settings = Settings()