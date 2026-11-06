"""Control-console contracts intentionally exclude secrets and user health data."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from server.schemas.admin_user import AdminUserRead


class PlanConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    model_name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_./:-]*$")
    timeout_seconds: int = Field(ge=10, le=600)
    ai_plan_daily_limit: int = Field(ge=0, le=1000)
    ai_plan_cooldown_seconds: int = Field(ge=0, le=86400)
    temperature: float = Field(ge=0, le=2, multiple_of=0.01, allow_inf_nan=False)
    top_p: float = Field(gt=0, le=1, multiple_of=0.01, allow_inf_nan=False)
    max_tokens_per_week: int = Field(ge=500, le=10000)
    max_tokens_cap: int = Field(ge=4096, le=128000)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: PlanConfig
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class AccountAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal['user', 'admin']
    status: Literal['active', 'disabled']
    expected_role: Literal['user', 'admin']
    expected_status: Literal['active', 'disabled']


class UserPage(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class RevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_user_id: int | None
    status: str
    config_json: PlanConfig
    created_at: datetime
    published_at: datetime | None


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_user_id: int | None
    action: str
    target_type: str
    target_id: int | None
    changed_fields: list[str]
    created_at: datetime
