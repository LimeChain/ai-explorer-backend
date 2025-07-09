"""
Configuration settings for the AI Explorer backend service.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        openai_api_key: OpenAI API key for LLM integration
        environment: Current environment (development, production, etc.)
        log_level: Logging level
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    openai_api_key: str
    environment: str = "development"
    log_level: str = "INFO"


# Global settings instance
settings = Settings()