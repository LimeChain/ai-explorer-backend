"""
Configuration settings for the MCP server.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field


class MCPSettings(BaseSettings):
    """
    MCP server settings loaded from environment variables.
    
    Attributes:
        vector_store_url: Connection string for the vector database
        openai_api_key: OpenAI API key for embeddings and AI operations
        collection_name: Name of the vector store collection
        embedding_model: Model to use for embeddings
        sdk_documentation_path: Path to the SDK documentation file
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    vector_store_url: str = Field(
        default="postgresql://ai_explorer:ai_explorer@localhost:5432/ai_explorer",
        description="Vector store connection URL"
    )
    
    openai_api_key: SecretStr = Field(
        description="OpenAI API key (required)"
    )
    
    collection_name: str = Field(
        default="sdk_methods",
        description="Vector store collection name"
    )
    
    embedding_model: str = Field(
        default="text-embedding-3-small",
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
    
    text_to_sql_model: str = Field(
        default="gpt-4.1-mini", 
        description="LLM model to use for SQL generation"
    )
    
    bigquery_query_timeout: int = Field(
        default=300,
        description="BigQuery query timeout in seconds"
    )


# Global settings instance
settings = MCPSettings()