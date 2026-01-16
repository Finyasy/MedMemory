from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    app_name: str = "MedMemory API"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # CORS settings
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # API settings
    api_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
