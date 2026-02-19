from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "MedMemory API"
    app_version: str = "0.1.0"
    debug: bool = False

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = [
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Requested-With",
    ]

    api_prefix: str = "/api/v1"

    database_url: str = Field(
        ...,
        description="PostgreSQL database URL. Must be set via DATABASE_URL environment variable.",
    )
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_pre_ping: bool = True
    database_pool_recycle: int = 1800
    database_init_retries: int = Field(
        default=30,
        ge=0,
        description="Number of retries for DB initialization at startup.",
    )
    database_init_retry_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        description="Base delay (seconds) between DB initialization retries.",
    )

    upload_dir: Path = Path("uploads")
    max_upload_size: int = 50 * 1024 * 1024
    allowed_extensions: list[str] = [
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".docx",
        ".txt",
    ]
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

    llm_model: str = "google/medgemma-1.5-4b-it"
    llm_model_path: Path | None = Field(
        default=None,
        description="Local path to model directory. If set, uses local model instead of downloading from HF.",
    )
    llm_use_mlx: bool = Field(
        default=True,
        description="Use MLX runtime for text generation on Apple Silicon when available.",
    )
    llm_mlx_quantized_model_path: Path | None = Field(
        default=None,
        description="Optional local path to a pre-quantized MLX model directory.",
    )
    llm_mlx_quantization_bits: int = Field(
        default=4,
        ge=0,
        le=8,
        description=(
            "Preferred MLX quantization level for local Apple Silicon inference. "
            "Set to 0 to disable MLX quantized model preference."
        ),
    )
    llm_quantize_4bit: bool = Field(
        default=True,
        description="Use 4-bit INT4 quantization for memory efficiency (requires CUDA and bitsandbytes)",
    )
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7
    llm_do_sample: bool = Field(
        default=False,
        description="Enable stochastic decoding (sampling). Keep false for deterministic clinical QA.",
    )
    llm_top_p: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter (used only when llm_do_sample=true).",
    )
    llm_top_k: int = Field(
        default=40,
        ge=1,
        description="Top-k sampling parameter (used only when llm_do_sample=true).",
    )
    llm_repetition_penalty: float = Field(
        default=1.1,
        ge=1.0,
        le=2.0,
        description="Repetition penalty applied during decoding to reduce loops/repetition.",
    )
    llm_prompt_profile: Literal[
        "baseline_current",
        "warm_concise_v1",
        "warm_concise_v2",
        "clinician_terse_humanized",
    ] = Field(
        default="warm_concise_v1",
        description=(
            "Prompt style profile selector for MedGemma chat tone experiments. "
            "Profiles tune tone only; grounding/citation/refusal guardrails remain active."
        ),
    )
    llm_max_new_tokens: int = 512
    llm_strict_grounding: bool = Field(
        default=True,
        description="Fail closed for factual queries when evidence is missing or low-confidence.",
    )
    llm_min_relevance_score: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum ranked relevance score for strict grounding factual answers.",
    )
    llm_low_confidence_floor: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description=(
            "Lower relevance floor for returning a low-confidence inferred response "
            "instead of hard refusal when strict grounding fails."
        ),
    )
    llm_allow_weak_fallback: bool = Field(
        default=False,
        description="Allow weak recent-chunk fallback when retrieval finds no matches.",
    )
    llm_require_numeric_citations: bool = Field(
        default=False,
        description=(
            "Require inline citations for numeric claims in all chat responses, not "
            "just clinician mode. When enabled, uncited numeric claims are refused."
        ),
    )
    llm_enable_self_correction: bool = Field(
        default=True,
        description=(
            "Retry once with a critique/correction prompt when numeric grounding "
            "finds unsupported claims."
        ),
    )
    llm_reasoning_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Temperature used for reasoning/summarization style intents.",
    )
    llm_reasoning_top_p: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Top-p used for reasoning/summarization style intents.",
    )
    llm_rerank_enabled: bool = Field(
        default=True,
        description="Enable cross-encoder reranking after initial retrieval.",
    )
    llm_rerank_model: str = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="Cross-encoder model used for second-stage reranking.",
    )
    llm_rerank_candidates: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of retrieval candidates to rerank with cross-encoder.",
    )
    llm_rerank_top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Top reranked chunks kept for strict factual intents.",
    )
    llm_rerank_min_score: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum cross-encoder rerank score for high-confidence retention.",
    )

    ocr_refinement_enabled: bool = True
    ocr_refinement_max_new_tokens: int = 384
    ocr_preprocess_opencv: bool = True

    vision_extraction_enabled: bool = True
    vision_extraction_max_new_tokens: int = 2000

    models_dir: Path = Field(
        default=Path("models"), description="Directory for storing downloaded models"
    )

    max_context_chunks: int = 10
    similarity_threshold: float = 0.5
    dashboard_low_confidence_threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence threshold below which values are excluded from automated "
            "dashboard highlights and alert evaluation."
        ),
    )
    dashboard_auto_evaluate_alerts_on_ingest: bool = Field(
        default=True,
        description=(
            "Automatically run watchlist alert evaluation after successful lab ingestion."
        ),
    )
    dashboard_auto_refresh_metric_summary_on_ingest: bool = Field(
        default=True,
        description=(
            "Automatically refresh daily metric highlights summary after lab ingestion."
        ),
    )
    dashboard_background_sync_enabled: bool = Field(
        default=True,
        description="Enable background incremental sync scheduler for data connections.",
    )
    dashboard_sync_poll_interval_seconds: int = Field(
        default=300,
        ge=15,
        le=3600,
        description="Polling interval for background dashboard sync scheduler.",
    )
    dashboard_sync_due_hours: int = Field(
        default=6,
        ge=1,
        le=168,
        description="Connections older than this are considered due for background sync.",
    )
    dashboard_sync_batch_size: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of due connections processed per sync cycle.",
    )
    provider_sync_live_enabled: bool = Field(
        default=False,
        description="Enable live external provider API sync for data connections.",
    )
    provider_sync_live_base_urls: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of provider slug/alias to FHIR base URL for live sync "
            "(JSON object in env var)."
        ),
    )
    provider_sync_live_bearer_tokens: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of provider slug/alias to bearer token for live provider APIs "
            "(JSON object in env var)."
        ),
    )
    provider_sync_live_api_keys: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of provider slug/alias to API key used as X-API-Key "
            "(JSON object in env var)."
        ),
    )
    provider_sync_live_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=180,
        description="HTTP timeout (seconds) for live provider sync requests.",
    )
    provider_sync_live_verify_ssl: bool = Field(
        default=True,
        description="Verify TLS certificates for live provider API requests.",
    )
    provider_sync_live_patient_identifier_system: str | None = Field(
        default=None,
        description=(
            "Optional FHIR identifier system for patient search, prepended as "
            "'system|value' when provided."
        ),
    )
    provider_sync_live_page_size: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="FHIR page size used for live provider resource pulls.",
    )
    provider_sync_live_max_pages_per_resource: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum paginated FHIR bundle pages fetched per resource type.",
    )
    provider_sync_live_fallback_to_local_scan: bool = Field(
        default=True,
        description=(
            "When true, provider sync falls back to local delta scan if live sync "
            "is disabled or missing provider endpoint config."
        ),
    )
    dashboard_metric_about_rag_enabled: bool = Field(
        default=True,
        description=(
            "Enable RAG-grounded generation for metric detail 'About' explanations."
        ),
    )
    dashboard_metric_about_context_chars: int = Field(
        default=2200,
        ge=500,
        le=10000,
        description="Maximum context characters sent to LLM for metric explanations.",
    )

    hf_token: str | None = Field(
        default=None,
        description="Hugging Face token for accessing models. Set via HF_TOKEN environment variable.",
    )
    hf_cache_dir: Path | None = None

    hf_hub_offline: bool = Field(
        default=False,
        description="Run Hugging Face Hub in offline mode. Set via HF_HUB_OFFLINE=1",
    )
    transformers_offline: bool = Field(
        default=False,
        description="Run Transformers in offline mode. Set via TRANSFORMERS_OFFLINE=1",
    )

    api_key: str | None = None
    log_level: str = "INFO"

    auth_rate_limit_window_seconds: int = 60
    auth_rate_limit_max_requests: int = 10

    response_cache_ttl_seconds: int = 10

    password_reset_token_expire_minutes: int = 60
    frontend_base_url: str = "http://localhost:5173"
    smtp_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    jwt_secret_key: str | None = Field(
        default=None,
        description="Secret key for JWT token signing. Set via JWT_SECRET_KEY environment variable.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
