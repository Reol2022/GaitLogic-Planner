from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mysql_host: str = Field(default="127.0.0.1", validation_alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", validation_alias="MYSQL_USER")
    mysql_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    mysql_database: str = Field(
        default="gaitlogic_planner", validation_alias="MYSQL_DATABASE"
    )
    jwt_secret_key: str | None = Field(default=None, validation_alias="JWT_SECRET_KEY")
    access_token_expire_days: int = Field(
        default=7,
        validation_alias="ACCESS_TOKEN_EXPIRE_DAYS",
    )
    backend_cors_origins: str = Field(
        default=(
            "http://localhost:5173,"
            "http://127.0.0.1:5173,"
            "http://localhost:4173,"
            "http://127.0.0.1:4173"
        ),
        validation_alias="BACKEND_CORS_ORIGINS",
    )
    backend_cors_origin_regex: str | None = Field(
        default=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+$",
        validation_alias="BACKEND_CORS_ORIGIN_REGEX",
    )
    ai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AI_API_KEY", "DEEPSEEK_API_KEY"),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("AI_BASE_URL", "DEEPSEEK_BASE_URL"),
    )
    deepseek_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias=AliasChoices("AI_MODEL", "DEEPSEEK_MODEL"),
    )
    deepseek_timeout_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices("AI_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT_SECONDS"),
    )
    ai_plan_daily_limit: int = Field(default=3, validation_alias="AI_PLAN_DAILY_LIMIT")
    ai_plan_cooldown_seconds: int = Field(default=60, validation_alias="AI_PLAN_COOLDOWN_SECONDS")
    weekly_review_prompt_override: str | None = Field(
        default=None, validation_alias="WEEKLY_REVIEW_PROMPT_OVERRIDE"
    )
    training_readiness_rollout_mode: str = Field(
        default="all", validation_alias="TRAINING_READINESS_ROLLOUT_MODE"
    )
    workout_import_rollout_mode: str = Field(
        default="off", validation_alias="WORKOUT_IMPORT_ROLLOUT_MODE"
    )
    garmin_sync_rollout_mode: str = Field(
        default="off", validation_alias="GARMIN_SYNC_ROLLOUT_MODE"
    )
    data_sync_rollout_mode: str = Field(
        default="inherit", validation_alias="DATA_SYNC_ROLLOUT_MODE"
    )
    data_sync_mock_provider_enabled: bool = Field(
        default=False, validation_alias="DATA_SYNC_MOCK_PROVIDER_ENABLED"
    )
    simplified_workflow_rollout_mode: str = Field(
        default="all", validation_alias="SIMPLIFIED_WORKFLOW_ROLLOUT_MODE"
    )
    garmin_token_encryption_key: str | None = Field(
        default=None, validation_alias="GARMIN_TOKEN_ENCRYPTION_KEY"
    )
    garmin_token_key_version: str = Field(
        default="v1", validation_alias="GARMIN_TOKEN_KEY_VERSION"
    )
    garmin_raw_retention_days: int = Field(
        default=90, validation_alias="GARMIN_RAW_RETENTION_DAYS"
    )
    garmin_initial_sync_days: int = Field(
        default=90, validation_alias="GARMIN_INITIAL_SYNC_DAYS"
    )
    garmin_incremental_overlap_days: int = Field(
        default=3, validation_alias="GARMIN_INCREMENTAL_OVERLAP_DAYS"
    )
    garmin_custom_sync_max_days: int = Field(
        default=365, validation_alias="GARMIN_CUSTOM_SYNC_MAX_DAYS"
    )
    garmin_composite_activity_max_gap_minutes: int = Field(
        default=90, validation_alias="GARMIN_COMPOSITE_ACTIVITY_MAX_GAP_MINUTES"
    )
    garmin_sync_worker_poll_seconds: int = Field(
        default=5, validation_alias="GARMIN_SYNC_WORKER_POLL_SECONDS"
    )
    garmin_sync_max_retries: int = Field(
        default=3, validation_alias="GARMIN_SYNC_MAX_RETRIES"
    )
    ai_readiness_explanation_enabled: bool = Field(
        default=False, validation_alias="AI_READINESS_EXPLANATION_ENABLED"
    )
    # Competition-only capabilities are opt-in and remain off in normal product
    # environments. Keep these checks centralized in settings.
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    competition_mode: bool = Field(default=False, validation_alias="COMPETITION_MODE")
    enable_experiment_dashboard: bool = Field(default=False, validation_alias="ENABLE_EXPERIMENT_DASHBOARD")
    enable_agent_trace: bool = Field(default=False, validation_alias="ENABLE_AGENT_TRACE")
    enable_survey_module: bool = Field(default=False, validation_alias="ENABLE_SURVEY_MODULE")
    enable_competition_demo_data: bool = Field(default=False, validation_alias="ENABLE_COMPETITION_DEMO_DATA")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}@"
            f"{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def server_url(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{user}:{password}@"
            f"{self.mysql_host}:{self.mysql_port}/?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            item.strip()
            for item in (self.backend_cors_origins or "").split(",")
            if item.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
