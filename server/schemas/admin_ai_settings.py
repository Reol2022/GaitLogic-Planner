from datetime import datetime

from pydantic import BaseModel, Field


class AdminAISettingsRead(BaseModel):
    id: int | None = None
    deepseek_base_url: str
    deepseek_model: str
    deepseek_timeout_seconds: int
    ai_plan_daily_limit: int
    ai_plan_cooldown_seconds: int
    temperature: float
    top_p: float
    max_tokens_per_week: int
    max_tokens_cap: int
    has_api_key: bool
    api_key_preview: str | None = None
    updated_at: datetime | None = None


class AdminAISettingsUpdate(BaseModel):
    deepseek_base_url: str = Field(min_length=1, max_length=255)
    deepseek_model: str = Field(min_length=1, max_length=64)
    deepseek_api_key: str | None = Field(default=None, max_length=512)
    deepseek_timeout_seconds: int = Field(ge=10, le=600)
    ai_plan_daily_limit: int = Field(ge=0, le=1000)
    ai_plan_cooldown_seconds: int = Field(ge=0, le=86400)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_tokens_per_week: int = Field(ge=500, le=10000)
    max_tokens_cap: int = Field(ge=4096, le=128000)
