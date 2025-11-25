"""Configuration management using environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MongoDB Configuration
    MONGO_URI: str
    MONGO_DB_NAME: str = "lumina"
    MONGO_COLLECTION_NAME: str = "documents"
    VECTOR_INDEX_NAME: str = "vector_index"

    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"

    # Azure OpenAI Configuration (alternative to OpenAI)
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_EMBEDDING_DEPLOYMENT: Optional[str] = None
    AZURE_LLM_DEPLOYMENT: Optional[str] = None

    # Application Configuration
    LOG_LEVEL: str = "INFO"
    MAX_CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5

    # API Configuration
    API_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    #Backend URL
    BACKEND_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def use_azure_openai(self) -> bool:
        """Check if Azure OpenAI is configured."""
        return bool(
            self.AZURE_OPENAI_ENDPOINT
            and self.AZURE_OPENAI_API_KEY
        )


# Global settings instance
settings = Settings()
