"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Centralized settings for EDUCORE AI PS3 backend."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EDUCORE AI - PS3 Early Dropout Prediction & Retention Copilot"
    app_env: str = "development"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/ps3"
    log_level: str = "INFO"

    database_url: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'educore_ps3.db').as_posix()}",
        description="PostgreSQL/Supabase or SQLite SQLAlchemy connection string.",
    )
    supabase_url: str = ""
    supabase_anon_key: str = ""

    max_upload_mb: int = Field(default=10, ge=1, le=100)
    max_validation_errors_returned: int = Field(default=200, ge=1, le=5000)

    auto_seed_synthetic_demo: bool = False
    synthetic_demo_record_count: int = Field(default=250, ge=200, le=10000)
    synthetic_random_seed: int = 42

    # Phase 2 ML Pipeline & Risk Classification Thresholds
    model_artifacts_dir: str = str(BASE_DIR / "artifacts" / "models")
    min_training_samples: int = Field(default=20, ge=10, le=10000)
    default_test_size: float = Field(default=0.2, gt=0.05, lt=0.5)
    rf_n_estimators: int = Field(default=200, ge=10, le=1000)
    rf_max_depth: int = Field(default=8, ge=2, le=50)
    rf_random_state: int = 42
    risk_threshold_medium: float = Field(default=0.35, gt=0.0, lt=1.0)
    risk_threshold_high: float = Field(default=0.70, gt=0.0, lt=1.0)
    threshold_profile: str = "demo_default"

    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"

    # Phase 5 Authentication, Session, CSRF, and Security Hardening
    session_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    session_max_lifetime_hours: int = Field(default=12, ge=1, le=168)
    session_cookie_name: str = "ps3_session"
    csrf_cookie_name: str = "ps3_csrf"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    login_rate_limit_attempts: int = Field(default=5, ge=2, le=50)
    login_rate_limit_window_minutes: int = Field(default=15, ge=1, le=1440)
    password_min_length: int = Field(default=10, ge=8, le=128)
    docs_enabled: bool = True
    enable_hsts: bool = False

    # Optional startup bootstrap administrator (only created when DB has zero users & password env var is explicitly set)
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_email: str = "admin@educore.local"
    bootstrap_admin_full_name: str = "System Administrator"
    bootstrap_admin_password: str = ""

    # Phase 5 Notification & Controlled Email Transport Settings
    notification_email_transport: str = "disabled"  # disabled | smtp | memory_test
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@educore.local"
    follow_up_approaching_hours: int = Field(default=24, ge=1, le=720)
    notification_max_retries: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def _validate_risk_thresholds(self) -> "Settings":
        """Ensure medium threshold sits strictly below high threshold and validate prod CORS."""
        if self.risk_threshold_medium >= self.risk_threshold_high:
            raise ValueError(
                "risk_threshold_medium must be strictly less than risk_threshold_high."
            )
        if self.app_env.strip().lower() == "production" and "*" in self.cors_origin_list:
            raise ValueError("Wildcard CORS origins ('*') are prohibited when APP_ENV=production.")
        return self

    @property
    def effective_docs_enabled(self) -> bool:
        """Disable interactive Swagger/OpenAPI docs in production unless explicitly overridden."""
        if self.app_env.strip().lower() == "production":
            return False
        return self.docs_enabled

    @property
    def resolved_model_artifacts_dir(self) -> Path:
        """Resolve model artifacts directory relative to PS3 root when not absolute."""
        path = Path(self.model_artifacts_dir)
        return path if path.is_absolute() else (BASE_DIR / path)

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def normalized_database_url(self) -> str:
        """Normalize legacy postgres:// URLs for SQLAlchemy compatibility."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql://" + url[len("postgres://") :]
        return url

    @property
    def max_upload_bytes(self) -> int:
        """Maximum allowed CSV upload size in bytes."""
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()

