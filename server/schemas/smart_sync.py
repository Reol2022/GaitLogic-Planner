from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SmartSyncSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    interval_minutes: int = Field(default=30, ge=30, le=1440)
    recovery_enabled: bool = False


class SmartSyncRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trigger: Literal['home', 'manual'] = 'home'


class SyncFreshness(BaseModel):
    status: str
    scope: str = 'activities'
    last_success_at: datetime | None = None
    last_success_by_scope: dict[str, datetime | None] = Field(default_factory=dict)
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    error_category: str | None = None
    job_id: int | None = None
    trigger_source: str | None = None
    enabled: bool = False
    interval_minutes: int = 30
    recovery_enabled: bool = False
    facts_read_at: datetime | None = None
    note: str = 'Sync timestamps describe successful fetches, not guaranteed upstream completeness.'

    @field_serializer('last_success_at', 'last_attempt_at', 'next_retry_at', 'facts_read_at', when_used='json')
    def utc_timestamp(self, value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None

    @field_serializer('last_success_by_scope', when_used='json')
    def utc_scopes(self, values):
        return {key: value.replace(tzinfo=timezone.utc).isoformat() if value else None for key, value in values.items()}
