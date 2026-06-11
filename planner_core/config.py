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


@lru_cache
def get_settings() -> Settings:
    return Settings()
