from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    app_name: str = "MedMemory API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    api_prefix: str = "/api/v1"
    
    database_url: str = "postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory"
    database_echo: bool = False
    
    upload_dir: Path = Path("uploads")
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".docx", ".txt"]
    
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    llm_model: str = "google/medgemma-4b-it"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7
    
    max_context_chunks: int = 10
    similarity_threshold: float = 0.5
    
    hf_token: Optional[str] = None
    hf_cache_dir: Optional[Path] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
