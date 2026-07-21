from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class GarminConnectionStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connected: bool
    connection_id: int | None = None
    status: str = "disconnected"
    provider: str = "garmin"
    region: str | None = None
    masked_account_identifier: str | None = None
    auto_import_enabled: bool = True
    auto_sync_enabled: bool = False
    auto_sync_last_run_at: datetime | None = None
    last_authenticated_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_error_code: str | None = None
    last_error_at: datetime | None = None


class GarminConnectRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    region: str | None = Field(default=None, max_length=32)


class GarminMfaRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=512)
    mfa_code: str = Field(min_length=1, max_length=32)


class GarminConnectResponse(BaseModel):
    status: str
    connection: GarminConnectionStatus | None = None
    mfa_token: str | None = None
    safe_message: str | None = None


class GarminSyncRequest(BaseModel):
    sync_mode: str = "incremental"
    start: datetime | None = None
    end: datetime | None = None


class GarminSyncSettingsUpdate(BaseModel):
    auto_import_enabled: bool


class ExternalSyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sync_run_id: str
    provider: str
    sync_mode: str
    requested_start: datetime | None
    requested_end: datetime | None
    status: str
    fetched_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    matched_count: int
    unplanned_count: int
    needs_review_count: int
    ignored_count: int
    failed_count: int
    is_committed: bool
    committed_at: datetime | None
    created_log_count: int
    updated_log_count: int
    unchanged_activity_count: int
    runner_state_affecting_change_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    safe_error_message: str | None
    created_at: datetime
    updated_at: datetime


class ExternalActivityLapRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lap_index: int
    distance_m: Decimal | None
    duration_seconds: int | None
    average_pace_seconds_per_km: int | None
    average_heart_rate_bpm: int | None
    segment_role: str
    classification_source: str
    classification_confidence: str
    data_quality: str


class ExternalActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    external_activity_id: str
    activity_name: str | None
    activity_type: str
    activity_date: date
    start_time_local: datetime
    processing_status: str
    resolution_status: str = "pending"
    apply_status: str = "not_applied"
    composite_session_key: str | None = None
    match_confidence: str | None
    planned_workout_id: int | None
    workout_log_id: int | None
    distance_m: Decimal | None
    duration_seconds: int | None
    average_pace_seconds_per_km: int | None
    average_heart_rate_bpm: int | None
    max_heart_rate_bpm: int | None
    data_quality: str
    quality_warnings_json: list | None = None


class GarminActivityResolutionRequest(BaseModel):
    action: str
    workout_log_id: int | None = None
    planned_workout_id: int | None = None
    reason: str | None = Field(default=None, max_length=255)


class GarminActivityReconcileRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    dry_run: bool = True
    activity_ids: list[int] | None = None


class GarminActivityReconcileSummary(BaseModel):
    dry_run: bool
    activity_count: int
    estimated_session_count: int
    estimated_matched_plan_count: int
    estimated_merged_existing_log_count: int
    estimated_unplanned_log_count: int
    needs_review_count: int
    conflict_count: int
    applied_count: int = 0
