from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus, urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"


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
    mcp_http_enabled: bool = Field(default=False, validation_alias="MCP_HTTP_ENABLED")
    mcp_http_host: str = Field(default="127.0.0.1", validation_alias="MCP_HTTP_HOST")
    mcp_allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="MCP_ALLOWED_ORIGINS",
    )
    mcp_allowed_hosts: str = Field(
        default="localhost:8000,127.0.0.1:8000",
        validation_alias="MCP_ALLOWED_HOSTS",
    )
    mcp_token_issuer: str = Field(
        default="gaitlogic-planner",
        min_length=1,
        max_length=128,
        validation_alias="MCP_TOKEN_ISSUER",
    )
    mcp_token_audience: str = Field(
        default="gaitlogic-mcp",
        min_length=1,
        max_length=128,
        validation_alias="MCP_TOKEN_AUDIENCE",
    )
    mcp_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=120,
        validation_alias="MCP_TOKEN_EXPIRE_MINUTES",
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
    agent_max_model_calls: int = Field(
        default=4,
        ge=1,
        le=8,
        validation_alias="AGENT_MAX_MODEL_CALLS",
    )
    agent_max_tool_rounds: int = Field(
        default=3,
        ge=0,
        le=7,
        validation_alias="AGENT_MAX_TOOL_ROUNDS",
    )
    agent_max_tool_calls: int = Field(
        default=6,
        ge=0,
        le=20,
        validation_alias="AGENT_MAX_TOOL_CALLS",
    )
    agent_max_same_tool_calls: int = Field(
        default=2,
        ge=1,
        le=6,
        validation_alias="AGENT_MAX_SAME_TOOL_CALLS",
    )
    agent_max_message_length: int = Field(
        default=4000,
        ge=1,
        le=12000,
        validation_alias="AGENT_MAX_MESSAGE_LENGTH",
    )
    agent_max_context_items: int = Field(
        default=50,
        ge=1,
        le=200,
        validation_alias="AGENT_MAX_CONTEXT_ITEMS",
    )
    agent_max_context_chars: int = Field(
        default=50000,
        ge=5000,
        le=50000,
        validation_alias="AGENT_MAX_CONTEXT_CHARS",
    )
    agent_max_recent_training_items: int = Field(
        default=20,
        ge=1,
        le=50,
        validation_alias="AGENT_MAX_RECENT_TRAINING_ITEMS",
    )
    agent_max_history_items: int = Field(
        default=7,
        ge=1,
        le=14,
        validation_alias="AGENT_MAX_HISTORY_ITEMS",
    )
    agent_max_evidence_items: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias="AGENT_MAX_EVIDENCE_ITEMS",
    )
    agent_max_rule_items: int = Field(
        default=20,
        ge=1,
        le=50,
        validation_alias="AGENT_MAX_RULE_ITEMS",
    )
    agent_max_answer_length: int = Field(
        default=6000,
        ge=1,
        le=12000,
        validation_alias="AGENT_MAX_ANSWER_LENGTH",
    )
    coach_agent_enabled: bool = Field(
        default=False,
        validation_alias="COACH_AGENT_ENABLED",
    )
    coach_agent_provider: str = Field(
        default="openai-compatible",
        min_length=1,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        validation_alias="COACH_AGENT_PROVIDER",
    )
    coach_agent_api_key: str | None = Field(
        default=None,
        validation_alias="COACH_AGENT_API_KEY",
    )
    coach_agent_base_url: str = Field(
        default="https://api.example.com/v1",
        max_length=2048,
        validation_alias="COACH_AGENT_BASE_URL",
    )
    coach_agent_model: str = Field(
        default="example-model",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
        validation_alias="COACH_AGENT_MODEL",
    )
    coach_agent_thinking_mode: Literal["unset", "disabled", "enabled"] = Field(
        default="unset",
        validation_alias="COACH_AGENT_THINKING_MODE",
    )
    coach_agent_response_format_mode: Literal["json_schema", "json_object"] = Field(
        default="json_schema",
        validation_alias="COACH_AGENT_RESPONSE_FORMAT_MODE",
    )
    coach_agent_connect_timeout_seconds: float = Field(
        default=10,
        gt=0,
        le=60,
        validation_alias="COACH_AGENT_CONNECT_TIMEOUT_SECONDS",
    )
    coach_agent_read_timeout_seconds: float = Field(
        default=60,
        gt=0,
        le=180,
        validation_alias="COACH_AGENT_READ_TIMEOUT_SECONDS",
    )
    coach_agent_total_timeout_seconds: float = Field(
        default=90,
        gt=0,
        le=300,
        validation_alias="COACH_AGENT_TOTAL_TIMEOUT_SECONDS",
    )
    coach_agent_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        validation_alias="COACH_AGENT_MAX_RETRIES",
    )
    coach_agent_retry_initial_backoff_seconds: float = Field(
        default=0.25,
        ge=0,
        le=10,
        validation_alias="COACH_AGENT_RETRY_INITIAL_BACKOFF_SECONDS",
    )
    coach_agent_retry_max_backoff_seconds: float = Field(
        default=1.0,
        ge=0,
        le=30,
        validation_alias="COACH_AGENT_RETRY_MAX_BACKOFF_SECONDS",
    )
    coach_agent_max_output_tokens: int = Field(
        default=2000,
        ge=256,
        le=65536,
        validation_alias="COACH_AGENT_MAX_OUTPUT_TOKENS",
    )
    coach_fact_query_model: str | None = Field(
        default=None, validation_alias="COACH_FACT_QUERY_MODEL"
    )
    coach_fact_query_max_output_tokens: int = Field(
        default=2048, ge=256, le=65536, validation_alias="COACH_FACT_QUERY_MAX_OUTPUT_TOKENS"
    )
    coach_analysis_model: str | None = Field(
        default=None, validation_alias="COACH_ANALYSIS_MODEL"
    )
    coach_analysis_max_output_tokens: int = Field(
        default=8192, ge=256, le=65536, validation_alias="COACH_ANALYSIS_MAX_OUTPUT_TOKENS"
    )
    weekly_review_model: str | None = Field(
        default=None, validation_alias="WEEKLY_REVIEW_MODEL"
    )
    weekly_review_max_output_tokens: int = Field(
        default=16384, ge=1024, le=65536, validation_alias="WEEKLY_REVIEW_MAX_OUTPUT_TOKENS"
    )
    weekly_review_timeout_seconds: int = Field(
        default=300, ge=30, le=600, validation_alias="WEEKLY_REVIEW_TIMEOUT_SECONDS"
    )
    plan_design_model: str | None = Field(
        default=None, validation_alias="PLAN_DESIGN_MODEL"
    )
    plan_design_max_output_tokens: int = Field(
        default=16384, ge=1024, le=65536, validation_alias="PLAN_DESIGN_MAX_OUTPUT_TOKENS"
    )
    plan_design_timeout_seconds: int = Field(
        default=300, ge=30, le=600, validation_alias="PLAN_DESIGN_TIMEOUT_SECONDS"
    )
    ai_plan_generation_model: str | None = Field(
        default=None, validation_alias="AI_PLAN_GENERATION_MODEL"
    )
    ai_plan_generation_max_output_tokens: int = Field(
        default=24000, ge=4096, le=65536, validation_alias="AI_PLAN_GENERATION_MAX_OUTPUT_TOKENS"
    )
    provider_task_max_retries: int = Field(
        default=2, ge=0, le=2, validation_alias="PROVIDER_TASK_MAX_RETRIES"
    )
    provider_task_retry_token_multiplier: float = Field(
        default=1.5, ge=1.0, le=2.0, validation_alias="PROVIDER_TASK_RETRY_TOKEN_MULTIPLIER"
    )
    weekly_reasoning_persistence_enabled: bool = Field(
        default=True, validation_alias="WEEKLY_REASONING_PERSISTENCE_ENABLED"
    )
    plan_design_reasoning_persistence_enabled: bool = Field(
        default=True, validation_alias="PLAN_DESIGN_REASONING_PERSISTENCE_ENABLED"
    )
    coach_agent_daily_limit: int = Field(
        default=30,
        ge=1,
        le=500,
        validation_alias="COACH_AGENT_DAILY_LIMIT",
    )
    coach_agent_cooldown_seconds: int = Field(
        default=3,
        ge=0,
        le=300,
        validation_alias="COACH_AGENT_COOLDOWN_SECONDS",
    )
    coach_agent_allow_local_provider_in_development: bool = Field(
        default=False,
        validation_alias="COACH_AGENT_ALLOW_LOCAL_PROVIDER_IN_DEVELOPMENT",
    )
    knowledge_embedding_enabled: bool = Field(
        default=False,
        validation_alias="KNOWLEDGE_EMBEDDING_ENABLED",
    )
    knowledge_embedding_provider: Literal["openai_compatible"] = Field(
        default="openai_compatible",
        validation_alias="KNOWLEDGE_EMBEDDING_PROVIDER",
    )
    knowledge_embedding_api_key: str | None = Field(
        default=None,
        validation_alias="KNOWLEDGE_EMBEDDING_API_KEY",
    )
    knowledge_embedding_base_url: str = Field(
        default="https://api.example.com/v1",
        max_length=2048,
        validation_alias="KNOWLEDGE_EMBEDDING_BASE_URL",
    )
    knowledge_embedding_model: str = Field(
        default="example-embedding-model",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
        validation_alias="KNOWLEDGE_EMBEDDING_MODEL",
    )
    knowledge_embedding_dimensions: int | None = Field(
        default=None,
        ge=1,
        le=65536,
        validation_alias="KNOWLEDGE_EMBEDDING_DIMENSIONS",
    )
    knowledge_embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=128,
        validation_alias="KNOWLEDGE_EMBEDDING_BATCH_SIZE",
    )
    knowledge_embedding_connect_timeout_seconds: float = Field(
        default=5,
        gt=0,
        le=60,
        validation_alias="KNOWLEDGE_EMBEDDING_CONNECT_TIMEOUT_SECONDS",
    )
    knowledge_embedding_read_timeout_seconds: float = Field(
        default=30,
        gt=0,
        le=180,
        validation_alias="KNOWLEDGE_EMBEDDING_READ_TIMEOUT_SECONDS",
    )
    knowledge_embedding_total_timeout_seconds: float = Field(
        default=60,
        gt=0,
        le=300,
        validation_alias="KNOWLEDGE_EMBEDDING_TOTAL_TIMEOUT_SECONDS",
    )
    knowledge_embedding_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
        validation_alias="KNOWLEDGE_EMBEDDING_MAX_RETRIES",
    )
    knowledge_embedding_retry_initial_backoff_seconds: float = Field(
        default=0.25,
        ge=0,
        le=10,
        validation_alias="KNOWLEDGE_EMBEDDING_RETRY_INITIAL_BACKOFF_SECONDS",
    )
    knowledge_embedding_retry_max_backoff_seconds: float = Field(
        default=1.0,
        ge=0,
        le=30,
        validation_alias="KNOWLEDGE_EMBEDDING_RETRY_MAX_BACKOFF_SECONDS",
    )
    knowledge_embedding_allow_local_provider_in_development: bool = Field(
        default=False,
        validation_alias=(
            "KNOWLEDGE_EMBEDDING_ALLOW_LOCAL_PROVIDER_IN_DEVELOPMENT"
        ),
    )
    coach_agent_knowledge_retrieval_enabled: bool = Field(
        default=False,
        validation_alias="COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED",
    )
    coach_agent_knowledge_index_id: str = Field(
        default="",
        max_length=80,
        pattern=r"^(?:|knowledge-[0-9a-f]{24})$",
        validation_alias="COACH_AGENT_KNOWLEDGE_INDEX_ID",
    )
    coach_agent_knowledge_bm25_index_id: str = Field(
        default="",
        max_length=80,
        pattern=r"^(?:|bm25-[0-9a-f]{24})$",
        validation_alias="COACH_AGENT_KNOWLEDGE_BM25_INDEX_ID",
    )
    knowledge_retrieval_strategy: Literal["dense", "bm25", "hybrid", "rerank"] = Field(
        default="dense",
        validation_alias="KNOWLEDGE_RETRIEVAL_STRATEGY",
    )
    knowledge_index_runtime_directory: str = Field(
        default="var/knowledge_indexes",
        min_length=1,
        max_length=240,
        validation_alias="KNOWLEDGE_INDEX_RUNTIME_DIRECTORY",
    )
    knowledge_bm25_index_runtime_directory: str = Field(
        default="var/knowledge_bm25_indexes",
        min_length=1,
        max_length=240,
        validation_alias="KNOWLEDGE_BM25_INDEX_RUNTIME_DIRECTORY",
    )
    knowledge_hybrid_fusion: Literal["rrf"] = Field(
        default="rrf",
        validation_alias="KNOWLEDGE_HYBRID_FUSION",
    )
    knowledge_hybrid_dense_candidates: int = Field(
        default=8, ge=4, le=12,
        validation_alias="KNOWLEDGE_HYBRID_DENSE_CANDIDATES",
    )
    knowledge_hybrid_bm25_candidates: int = Field(
        default=8, ge=4, le=12,
        validation_alias="KNOWLEDGE_HYBRID_BM25_CANDIDATES",
    )
    knowledge_reranker_enabled: bool = Field(
        default=False,
        validation_alias="KNOWLEDGE_RERANKER_ENABLED",
    )
    knowledge_reranker_provider: Literal["siliconflow"] = Field(
        default="siliconflow",
        validation_alias="KNOWLEDGE_RERANKER_PROVIDER",
    )
    knowledge_reranker_api_key: str | None = Field(
        default=None,
        validation_alias="KNOWLEDGE_RERANKER_API_KEY",
    )
    knowledge_reranker_base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        max_length=2048,
        validation_alias="KNOWLEDGE_RERANKER_BASE_URL",
    )
    knowledge_reranker_model: str = Field(
        default="Qwen/Qwen3-Reranker-0.6B",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
        validation_alias="KNOWLEDGE_RERANKER_MODEL",
    )
    knowledge_reranker_connect_timeout_seconds: float = Field(
        default=5, gt=0, le=60,
        validation_alias="KNOWLEDGE_RERANKER_CONNECT_TIMEOUT_SECONDS",
    )
    knowledge_reranker_read_timeout_seconds: float = Field(
        default=20, gt=0, le=180,
        validation_alias="KNOWLEDGE_RERANKER_READ_TIMEOUT_SECONDS",
    )
    knowledge_reranker_total_timeout_seconds: float = Field(
        default=30, gt=0, le=300,
        validation_alias="KNOWLEDGE_RERANKER_TOTAL_TIMEOUT_SECONDS",
    )
    knowledge_reranker_max_retries: int = Field(
        default=1, ge=0, le=3,
        validation_alias="KNOWLEDGE_RERANKER_MAX_RETRIES",
    )
    knowledge_reranker_retry_initial_backoff_seconds: float = Field(
        default=0.25, ge=0, le=10,
        validation_alias="KNOWLEDGE_RERANKER_RETRY_INITIAL_BACKOFF_SECONDS",
    )
    knowledge_reranker_retry_max_backoff_seconds: float = Field(
        default=1.0, ge=0, le=30,
        validation_alias="KNOWLEDGE_RERANKER_RETRY_MAX_BACKOFF_SECONDS",
    )
    knowledge_vector_store: Literal["exact", "qdrant"] = Field(
        default="exact",
        validation_alias="KNOWLEDGE_VECTOR_STORE",
    )
    qdrant_url: str | None = Field(
        default=None,
        validation_alias="QDRANT_URL",
    )
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias="QDRANT_API_KEY",
    )
    qdrant_collection_prefix: str = Field(
        default="gaitlogic",
        pattern=r"^[a-z][a-z0-9_-]{0,40}$",
        validation_alias="QDRANT_COLLECTION_PREFIX",
    )
    knowledge_index_max_age_days: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias="KNOWLEDGE_INDEX_MAX_AGE_DAYS",
    )
    coach_agent_knowledge_top_k: int = Field(
        default=4,
        ge=1,
        le=6,
        validation_alias="COACH_AGENT_KNOWLEDGE_TOP_K",
    )
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
    agent_tracing_enabled: bool = Field(
        default=False,
        validation_alias="AGENT_TRACING_ENABLED",
    )
    agent_trace_exporter: Literal["noop", "otlp"] = Field(
        default="noop",
        validation_alias="AGENT_TRACE_EXPORTER",
    )
    agent_metrics_enabled: bool = Field(
        default=False,
        validation_alias="AGENT_METRICS_ENABLED",
    )
    agent_metrics_max_latency_samples: int = Field(
        default=2048,
        ge=64,
        le=10000,
        validation_alias="AGENT_METRICS_MAX_LATENCY_SAMPLES",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        max_length=512,
        validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    enable_survey_module: bool = Field(default=False, validation_alias="ENABLE_SURVEY_MODULE")
    enable_competition_demo_data: bool = Field(default=False, validation_alias="ENABLE_COMPETITION_DEMO_DATA")

    model_config = SettingsConfigDict(
        # Resolve the development env file independently from the shell's cwd.
        # Uvicorn/reload workers may otherwise silently fall back to localhost.
        env_file=PROJECT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("otel_exporter_otlp_endpoint")
    @classmethod
    def validate_otel_endpoint(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OTLP endpoint must be an http(s) URL without credentials or query data")
        return value.rstrip("/")

    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Qdrant URL must be an http(s) URL without credentials or query data"
            )
        return value.rstrip("/")

    @field_validator("mcp_allowed_origins")
    @classmethod
    def validate_mcp_allowed_origins(cls, value: str) -> str:
        for origin in (item.strip() for item in value.split(",") if item.strip()):
            parsed = urlparse(origin)
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.params
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("MCP origins must be exact http(s) origins without wildcard or path")
        return value

    @field_validator("mcp_allowed_hosts")
    @classmethod
    def validate_mcp_allowed_hosts(cls, value: str) -> str:
        if any("*" in host for host in value.split(",")):
            raise ValueError("MCP allowed hosts must not contain wildcard values")
        return value

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

    @property
    def mcp_allowed_origins_list(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.mcp_allowed_origins.split(",") if item.strip()]

    @property
    def mcp_allowed_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.mcp_allowed_hosts.split(",") if item.strip()]

    @property
    def knowledge_reranker_effective_api_key(self) -> str | None:
        """Reuse the configured SiliconFlow embedding credential when safe.

        Reranking is an explicit opt-in feature, but SiliconFlow's embedding and
        rerank endpoints can share one account credential.  This avoids asking
        operators to duplicate a secret while never borrowing credentials from
        an unrelated embedding endpoint.
        """

        if self.knowledge_reranker_api_key:
            return self.knowledge_reranker_api_key
        embedding_host = (urlparse(self.knowledge_embedding_base_url).hostname or "").lower()
        if (
            self.knowledge_embedding_provider == "openai_compatible"
            and embedding_host == "api.siliconflow.cn"
        ):
            return self.knowledge_embedding_api_key
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
