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
        llm_api_key: API key for LLM integration (OpenAI, Google Gemini, Anthropic, etc.)
        llm_provider: LLM provider to use (openai, google_genai, anthropic, etc.)
        llm_model: The LLM model to use
        environment: Current environment (development, production, etc.)
        log_level: Logging level
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    embedding_model: str = Field(..., description="The model to use for embeddings")
    llm_provider: str = Field(..., description="LLM provider to use (openai, google_genai, anthropic, etc.)")
    llm_model: str = Field(..., description="The LLM model to use (e.g., gpt-4o, gpt-4o-mini for OpenAI; gemini-2.5-pro for Google)")
    llm_api_key: SecretStr = Field(..., description="LLM API key (required)", alias="LLM_API_KEY")
    
    # Token pricing settings
    llm_input_cost_per_token: float = Field(default=0.0000004, ge=0, description="Cost per input token in USD")
    llm_output_cost_per_token: float = Field(default=0.0000016, ge=0, description="Cost per output token in USD")

    environment: str = Field(..., pattern="^(development|production|staging)$")
    log_level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    mcp_endpoint: str = Field(..., description="MCP server endpoint")
    allowed_origins: List[str] = Field(..., description="List of allowed CORS origins")

    langsmith_tracing: bool = Field(..., description="Enable LangSmith tracing")
    langsmith_project: str = Field(..., description="LangSmith project name")
    langsmith_api_key: SecretStr = Field(..., description="LangSmith API key (required)")
    langsmith_endpoint: str = Field(..., description="LangSmith API endpoint")

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
    database_url: str = Field(..., description="Database connection URL")
    database_pool_size: int = Field(
        default=50, 
        ge=5, 
        le=200, 
        description="Database connection pool size (5-200 connections)"
    )
    database_max_overflow: int = Field(
        default=20, 
        ge=0, 
        le=100, 
        description="Database connection pool max overflow (0-100 connections)"
    )
    database_pool_timeout: int = Field(
        default=30, 
        ge=5, 
        le=60, 
        description="Database connection pool timeout in seconds (5-60s)"
    )
    database_pool_recycle: int = Field(
        default=3600,
        ge=300,
        le=7200, 
        description="Database connection recycle time in seconds (5min-2hr)"
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        description="Enable pool pre-ping to handle disconnected connections"
    )
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")

    # Vector store settings
    collection_name: str = Field(..., description="Vector store collection name")

    # Redis settings
    redis_url: str = Field(..., description="Redis connection URL")
    redis_max_connections: int = Field(default=20, description="Redis connection pool max connections")
    redis_retry_on_timeout: bool = Field(default=True, description="Redis retry on timeout")
    redis_socket_timeout: float = Field(default=5.0, description="Redis socket timeout in seconds")
    
    # Rate limiting settings
    rate_limit_max_requests: int = Field(..., ge=1, description="Max requests per window per IP")
    rate_limit_window_seconds: int = Field(..., ge=1, description="Rate limiting window in seconds")
    
    # Global rate limiting settings
    global_rate_limit_max_requests: int = Field(..., ge=1, description="Max total requests per window across all IPs")
    global_rate_limit_window_seconds: int = Field(..., ge=1, description="Global rate limiting window in seconds")
    
    # Cost-based rate limiting settings
    per_user_cost_limit: float = Field(..., ge=0, description="Max cost per user per period in USD")
    per_user_cost_period_seconds: int = Field(..., ge=1, description="User cost limit period in seconds (86400 = 1 day)")
    
    global_cost_limit: float = Field(..., ge=0, description="Max total cost across all users per period in USD")
    global_cost_period_seconds: int = Field(..., ge=1, description="Global cost limit period in seconds (31536000 = 1 year)")

# Global settings instance
settings = Settings()
