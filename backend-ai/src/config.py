"""Application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)


class Settings(BaseSettings):
    """Application settings from environment."""

    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/equity_research"

    # Redis (optional)
    redis_url: Optional[str] = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None


    # LLM
    llm_provider: Literal["ollama", "deepseek", "openai", "groq", "claude"] = "groq"
    # Optional global override model from .env (takes priority if set)
    llm_model: Optional[str] = None
    # Optional documented list for UI/ops discoverability, comma-separated in .env
    llm_model_options: Optional[str] = None
    llm_temperature: float = 0.3
    # Cap response length to keep generation time within UI timeouts.
    llm_max_tokens: int = 2048
    # gpt-oss / o-series reasoning effort: "low" | "medium" | "high" (low = fastest,
    # bounds the model's "thinking" time which was the main latency culprit).
    llm_reasoning_effort: Optional[str] = "low"

    # Provider-specific default chat models
    ollama_model: str = "deepseek-r1:8b"
    deepseek_model: str = "deepseek-chat"
    openai_model: str = "gpt-4o-mini"
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # DeepSeek API (when llm_provider=deepseek)
    deepseek_api_key: Optional[str] = None
    # Optional second key for automatic failover on timeout / rate-limit (429)
    deepseek_api_key_2: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_timeout: int = 240
    openai_api_key: Optional[str] = None

    # Groq API (when llm_provider=groq)
    groq_api_key: Optional[str] = "dkdkvm"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout: int = 60

    # Anthropic / Claude API (when llm_provider=claude)
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-6"

    # Gemini API (for supplemental company enrichment)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Embeddings (Ollama local / OpenAI)
    embedding_provider: str = "ollama"  # ollama | openai
    embedding_model: str = "nomic-embed-text"  # For Ollama
    embedding_dim: int = 768  # nomic=768, openai-3-small=1536

    # S3 / Object storage (optional)
    s3_bucket: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "ap-south-1"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: Optional[str] = None

    # Observability
    observability_enabled: bool = False
    observability_service_name: str = "lakshya-backend"
    observability_service_version: str = "0.2.0"
    otel_exporter_otlp_endpoint: Optional[str] = None
    otel_exporter_otlp_headers: Optional[str] = None
    otel_exporter_otlp_protocol: str = "http/protobuf"
    langsmith_tracing: bool = False
    langsmith_project: str = "lakshya-backend"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: Optional[str] = None

    # Deep multi-agent orchestration
    workflow_runs_dir: str = "workflow_runs"
    deep_agent_max_steps: int = 6
    chat_worker_pool_size: int = 4

    # Optional web search augmentation
    tavily_api_key: Optional[str] = None

    # External data API keys
    fmp_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    newsdata_api_key: Optional[str] = None

    # Commodity API keys (free tiers)
    oil_price_api_key: Optional[str] = None
    commodity_price_api_key: Optional[str] = None
    gdelt_api_key: Optional[str] = None

    # News NLP (Hugging Face)
    news_sentiment_model: str = "ProsusAI/finbert"
    news_zero_shot_model: str = "typeform/distilbert-base-uncased-mnli"

    # Upstox
    upstox_api_key: Optional[str] = None
    upstox_api_secret: Optional[str] = None
    upstox_access_token: Optional[str] = None

    # Kite Connect (Zerodha)
    kite_api_key: Optional[str] = None
    kite_api_secret: Optional[str] = None
    kite_access_token: Optional[str] = None

    # Auth / JWT
    jwt_secret_key: str = "change-me-in-production-use-a-real-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # OTP
    otp_expiry_minutes: int = 5
    otp_length: int = 6
    otp_max_attempts: int = 3
    otp_rate_limit_per_hour: int = 5

    # SMTP / Email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = "noreply@lakshya.ai"
    smtp_use_tls: bool = True

    # Cookie config (cross-domain)
    cookie_domain: Optional[str] = None
    cookie_secure: bool = False  # True for production cross-domain
    cookie_samesite: str = "lax"  # "none" for production cross-domain
    cookie_access_max_age: int = 1800
    cookie_refresh_max_age: int = 604800

    # Frontend URL (for OTP email links / redirects)
    frontend_url: str = "http://localhost:5173"

    # Additional CORS configuration for allowed origins
    allowed_origins: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_llm_model(self, override_model: Optional[str] = None) -> str:
        """Resolve active model name from explicit override, generic env var, or provider default."""
        if override_model:
            return override_model
        if self.llm_model:
            return self.llm_model
        if self.llm_provider == "ollama":
            return self.ollama_model
        if self.llm_provider == "deepseek":
            return self.deepseek_model
        if self.llm_provider == "openai":
            return self.openai_model
        if self.llm_provider == "groq":
            return self.groq_model
        if self.llm_provider == "claude":
            return self.claude_model
        return self.ollama_model

    @property
    def cors_origins(self):
        """Get allowed CORS origins from environment variable or default to localhost."""
        if self.allowed_origins:
            return self.allowed_origins.split(",")
        return ["*"]  # Default to allow all in development


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
