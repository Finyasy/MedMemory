from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    app_name: str = "MedMemory API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["Authorization", "Content-Type", "X-API-Key", "X-Requested-With"]
    
    api_prefix: str = "/api/v1"
    
    # Database configuration - REQUIRED via environment variable DATABASE_URL
    # Format: postgresql+asyncpg://user:password@host:port/database
    # Security: No default value to prevent hardcoded credentials
    database_url: str = Field(
        ...,
        description="PostgreSQL database URL. Must be set via DATABASE_URL environment variable."
    )
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_pre_ping: bool = True
    database_pool_recycle: int = 1800
    
    upload_dir: Path = Path("uploads")
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".docx", ".txt"]
    allowed_mime_types: list[str] = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]
    
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # LLM configuration
    llm_model: str = "google/medgemma-1.5-4b-it"  # Hugging Face model ID
    llm_model_path: Optional[Path] = Field(
        default=None,
        description="Local path to model directory. If set, uses local model instead of downloading from HF."
    )
    llm_quantize_4bit: bool = Field(
        default=True,
        description="Use 4-bit INT4 quantization for memory efficiency (requires CUDA and bitsandbytes)"
    )
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7
    llm_max_new_tokens: int = 512

    # OCR refinement configuration
    ocr_refinement_enabled: bool = True
    ocr_refinement_max_new_tokens: int = 384
    ocr_preprocess_opencv: bool = True
    
    # Models directory
    models_dir: Path = Field(
        default=Path("models"),
        description="Directory for storing downloaded models"
    )
    
    max_context_chunks: int = 10
    similarity_threshold: float = 0.5
    
    hf_token: Optional[str] = Field(
        default=None,
        description="Hugging Face token for accessing models. Set via HF_TOKEN environment variable."
    )
    hf_cache_dir: Optional[Path] = None

    api_key: Optional[str] = None
    log_level: str = "INFO"

    auth_rate_limit_window_seconds: int = 60
    auth_rate_limit_max_requests: int = 10

    response_cache_ttl_seconds: int = 10

    password_reset_token_expire_minutes: int = 60
    frontend_base_url: str = "http://localhost:5173"
    smtp_enabled: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_use_tls: bool = True
    
    # JWT Authentication
    jwt_secret_key: Optional[str] = Field(
        default=None,
        description="Secret key for JWT token signing. Set via JWT_SECRET_KEY environment variable.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15  # Short-lived access tokens
    jwt_refresh_token_expire_days: int = 7  # Long-lived refresh tokens

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if not self.jwt_secret_key:
            if self.debug:
                self.jwt_secret_key = "dev-secret-change-me"
            else:
                raise ValueError("JWT_SECRET_KEY must be set when DEBUG is false.")
        return self


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
