from datetime import datetime

from pydantic import BaseModel, Field


class AdminAISettingsRead(BaseModel):
    id: int | None = None
    provider: str
    base_url: str
    model_name: str
    timeout_seconds: int
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
    provider: str = Field(default="custom", min_length=1, max_length=32)
    base_url: str = Field(min_length=1, max_length=255)
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    timeout_seconds: int = Field(ge=10, le=600)
    ai_plan_daily_limit: int = Field(ge=0, le=1000)
    ai_plan_cooldown_seconds: int = Field(ge=0, le=86400)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_tokens_per_week: int = Field(ge=500, le=10000)
    max_tokens_cap: int = Field(ge=4096, le=128000)
