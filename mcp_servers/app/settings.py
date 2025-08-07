"""
Configuration settings for the MCP server.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field


class MCPSettings(BaseSettings):
    """
    MCP server settings loaded from environment variables.
    
    Attributes:
        database_url: Connection string for the vector database
        llm_api_key: OpenAI API key for embeddings and AI operations
        collection_name: Name of the vector store collection
        embedding_model: Model to use for embeddings
        sdk_documentation_path: Path to the SDK documentation file
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    database_url: str = Field(
        description="Database connection URL"
    )
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=5, description="Database connection pool max overflow")
    database_pool_timeout: int = Field(default=30, description="Database connection pool timeout in seconds")
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")
    
    llm_api_key: SecretStr = Field(
        description="LLM API key (required)"
    )
    
    collection_name: str = Field(
        default="sdk_methods",
        description="Vector store collection name"
    )
    
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="The model to use for embeddings",
    )
    
    sdk_documentation_path: str = Field(
        default="hiero_mirror_sdk_methods_documentation.json",
        description="Path to the SDK documentation file"
    )


# Global settings instance
settings = MCPSettings()