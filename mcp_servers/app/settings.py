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
        llm_model: Model to use for LLM
        llm_api_key: API key for LLM
        llm_provider: Provider to use for LLM
        collection_name: Name of the vector store collection
        embedding_model: Model to use for embeddings
        sdk_documentation_path: Path to the SDK documentation file
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    llm_model: str = Field(
        default="gpt-4.1-mini", 
        description="LLM model to use for SQL generation"
    )

    llm_api_key: SecretStr = Field(
        description="LLM API key (required)"
    )

    llm_provider: str = Field(
        default="openai",
        description="LLM provider to use (openai, google_genai, anthropic, etc.)"
    )
    
    database_url: str = Field(
        description="Vector store connection URL"
    )
    
    collection_name: str = Field(
        default="sdk_methods",
        description="Vector store collection name"
    )
    
    embedding_model: str = Field(
        default="text-embedding-ada-002",
        description="The model to use for embeddings"
    )
    
    sdk_documentation_path: str = Field(
        default="hiero_mirror_sdk_methods_documentation.json",
        description="Path to the SDK documentation file"
    )
    
    # BigQuery settings for text-to-SQL functionality
    bigquery_credentials_path: str = Field(
        default="bq-credentials.json",
        description="Path to BigQuery service account credentials JSON file"
    )
    
    bigquery_dataset_id: str = Field(
        default="hedera-etl-bq.hedera_restricted",
        description="BigQuery dataset ID for Hedera data"
    )

    cost_threshold: float = Field(
        default=0.01,
        description="Cost threshold for BigQuery queries"
    )

    bigquery_query_timeout: int = Field(
        default=300,
        description="BigQuery query timeout in seconds"
    )


# Global settings instance
settings = MCPSettings()