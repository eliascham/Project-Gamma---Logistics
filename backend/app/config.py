from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    environment: str = "development"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://gamma:gamma_dev_password@postgres:5432/project_gamma"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_haiku_model: str = "claude-haiku-4-5-20251001"
    claude_max_tokens: int = 4096

    # Voyage AI (embeddings)
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    embedding_dimensions: int = 1024

    # Cost allocation
    allocation_confidence_threshold: float = 0.85

    # RAG
    rag_top_k: int = 5
    rag_max_context_chars: int = 8000

    # File storage
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50

    # Allowed file types for upload
    allowed_file_types: set[str] = {"pdf", "png", "jpg", "jpeg", "tiff", "tif", "csv"}

    # HITL workflow
    hitl_auto_approve_dollar_threshold: float = 1000.0
    hitl_high_risk_dollar_threshold: float = 10000.0

    # Anomaly detection
    anomaly_budget_overrun_threshold: float = 0.1
    anomaly_duplicate_window_days: int = 90

    # MCP server
    mcp_server_port: int = 3001

    # Sentry (optional)
    sentry_dsn: str = ""


settings = Settings()
