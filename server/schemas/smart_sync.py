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


class SyncJobSnapshot(BaseModel):
    """User-scoped, safe job receipt; never expose raw Provider errors."""
    job_id: int
    scope: str
    status: str
    outcome: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    requested_start: datetime | None = None
    requested_end: datetime | None = None
    fetched_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    needs_review_count: int = 0
    committed: bool = False
    error_category: str | None = None

    @field_serializer('started_at', 'finished_at', 'requested_start', 'requested_end', when_used='json')
    def utc_timestamp(self, value):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if value else None


class SyncFreshness(BaseModel):
    status: str
    sync_status: str = 'UNKNOWN'
    data_freshness: Literal['FRESH', 'STALE', 'UNKNOWN'] = 'UNKNOWN'
    data_freshness_by_scope: dict[str, Literal['FRESH', 'STALE', 'UNKNOWN']] = Field(default_factory=dict)
    scope: str = 'activities'
    last_success_at: datetime | None = None
    last_success_by_scope: dict[str, datetime | None] = Field(default_factory=dict)
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    error_category: str | None = None
    job_id: int | None = None
    # job_id retains its legacy active-matching-job meaning. Terminal receipts
    # remain visible independently; an unrelated scope is never our queued job.
    last_job: SyncJobSnapshot | None = None
    last_job_by_scope: dict[str, SyncJobSnapshot | None] = Field(default_factory=dict)
    blocking_job: SyncJobSnapshot | None = None
    trigger_source: str | None = None
    enabled: bool = False
    interval_minutes: int = 30
    recovery_enabled: bool = False
    facts_read_at: datetime | None = None
    note: str = 'Sync timestamps describe successful fetches, not guaranteed upstream completeness.'

    @field_serializer('last_success_at', 'last_attempt_at', 'next_retry_at', 'facts_read_at', when_used='json')
    def utc_timestamp(self, value):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if value is not None else None

    @field_serializer('last_success_by_scope', when_used='json')
    def utc_scopes(self, values):
        return {key: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if value else None for key, value in values.items()}
