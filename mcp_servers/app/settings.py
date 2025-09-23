"""
Configuration settings for the MCP server.
"""

from pathlib import Path
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
        env_file=[
            Path(__file__).parent.parent / ".env", # mcp_servers/.env
            ".env",  # fallback to current dir
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    force_terminal: bool = Field(default=False, description="Force terminal output for Rich console")
    
    llm_provider: str = Field(description="LLM provider to use (openai, google_genai, anthropic, etc.)")
    llm_model: str = Field(description="The LLM model to use (e.g., gpt-4o, gpt-4o-mini for OpenAI; gemini-2.5-pro for Google)")
    llm_api_key: SecretStr = Field(description="LLM API key (required)")
    
    embedding_model: str = Field(description="The model to use for embeddings")
    
    collection_name: str = Field(default="sdk_methods", description="Vector store collection name")

    sdk_documentation_path: str = Field(
        default="mcp_servers/hiero_mirror_sdk_methods.json",
        description="Path to the SDK documentation file"
    )

    # Database settings
    database_url: str = Field(description="Database connection URL")
    database_pool_size: int = Field(
        default=30, 
        ge=5, 
        le=200, 
        description="Database connection pool size"
    )
    database_max_overflow: int = Field(
        default=10, 
        ge=0, 
        le=100, 
        description="Database connection pool max overflow"
    )
    database_pool_timeout: int = Field(
        default=30, 
        ge=5, 
        le=60, 
        description="Database connection pool timeout in seconds (5-60s)"
    )
    database_pool_recycle: int = Field(
        default=7200,
        ge=300,
        le=7200, 
        description="Database connection recycle time in seconds"
    )
    database_pool_pre_ping: bool = Field(
        default=True,
        description="Enable pool pre-ping to handle disconnected connections"
    )
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")

    # SaucerSwap API configuration
    saucerswap_api_key: SecretStr = Field(
        description="SaucerSwap API key for real-time token pricing"
    )
    saucerswap_base_url: str = Field(
        default="https://api.saucerswap.finance",
        description="Base URL for SaucerSwap API"
    )
    hbar_token_id: str = Field(
        default="0.0.1456986",
        description="HBAR token ID for SaucerSwap API calls"
    )

    # Hgraph GraphQL settings 
    hgraph_mainnet_endpoint: str = Field(
        default="https://mainnet.hedera.api.hgraph.io/v1/graphql",
        description="Hgraph GraphQL endpoint URL for Hedera mainnet"
    )
    
    hgraph_testnet_endpoint: str = Field(
        default="https://testnet.hedera.api.hgraph.io/v1/graphql", 
        description="Hgraph GraphQL endpoint URL for Hedera testnet"
    )
    
    hgraph_api_key: SecretStr = Field(
        description="API key for Hgraph authentication"
    )
    
    hgraph_graphql_schema_path: str = Field(
        default="mcp_servers/hgraph_graphql_schema.json",
        description="Path to the GraphQL schema introspection JSON file"
    )

    hgraph_graphql_metadata_path: str = Field(
        default="mcp_servers/hgraph_graphql_metadata.json",
        description="Path to the GraphQL metadata JSON file"
    )


settings = MCPSettings()