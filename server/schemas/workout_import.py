from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


WorkoutImportMergeStrategy = Literal[
    "create_missing_only",
    "fill_empty_fields",
    "update_objective_fields",
    "manual_review",
]
WorkoutImportAction = Literal[
    "create_log",
    "fill_empty_fields",
    "update_objective_fields",
    "keep_existing",
    "link_to_plan",
    "create_unplanned_log",
    "skip",
    "manual_review",
]


class NormalizedWorkoutActivity(BaseModel):
    activity_date: date
    start_time: time | None = None
    timezone: str | None = None
    session_index: int = Field(default=1, ge=1, le=9)
    sport_type: str = "running"
    workout_type: str | None = None
    title: str | None = None
    planned_workout_id: int | None = None
    distance_km: Decimal | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    moving_time_seconds: int | None = Field(default=None, ge=0)
    elapsed_time_seconds: int | None = Field(default=None, ge=0)
    average_pace_seconds_per_km: int | None = Field(default=None, ge=0)
    average_heart_rate_bpm: int | None = Field(default=None, ge=0)
    max_heart_rate_bpm: int | None = Field(default=None, ge=0)
    average_cadence_spm: int | None = Field(default=None, ge=0)
    max_cadence_spm: int | None = Field(default=None, ge=0)
    elevation_gain_m: int | None = Field(default=None, ge=0)
    calories_kcal: int | None = Field(default=None, ge=0)
    rpe: int | None = Field(default=None, ge=0, le=10)
    pain_level: int | None = Field(default=None, ge=0, le=10)
    completion_status: Literal["completed"] = "completed"
    content: str | None = None
    notes: str | None = None
    external_activity_id: str | None = None
    source: str | None = None

    @field_validator("sport_type")
    @classmethod
    def normalize_sport_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("sport_type 不能为空。")
        return normalized


class WorkoutImportStructuredRequest(BaseModel):
    source: str = "structured_json"
    timezone: str = "Asia/Shanghai"
    merge_strategy: WorkoutImportMergeStrategy = "create_missing_only"
    client_request_id: str | None = None
    activities: list[NormalizedWorkoutActivity]

    @model_validator(mode="after")
    def validate_activities(self) -> "WorkoutImportStructuredRequest":
        if not self.activities:
            raise ValueError("activities 不能为空。")
        return self


class WorkoutImportIssue(BaseModel):
    code: str
    message: str
    row_number: int | None = None
    field: str | None = None


class WorkoutImportFieldDiff(BaseModel):
    field: str
    existing_value: Any = None
    incoming_value: Any = None
    existing_source: str | None = None
    incoming_source: str | None = None
    recommended_action: str


class WorkoutImportPreviewSummary(BaseModel):
    total_count: int = 0
    matched_plan_count: int = 0
    matched_log_count: int = 0
    unplanned_count: int = 0
    ready_count: int = 0
    conflict_count: int = 0
    invalid_count: int = 0
    skipped_count: int = 0


class WorkoutImportItemPatch(BaseModel):
    normalized_data: NormalizedWorkoutActivity | None = None
    matched_plan_id: int | None = None
    session_index: int | None = Field(default=None, ge=1, le=9)
    workout_type: str | None = None
    user_action: WorkoutImportAction | None = None


class WorkoutImportItemRead(BaseModel):
    id: int
    row_number: int | None = None
    activity_date: date | None = None
    start_time: time | None = None
    session_index: int | None = None
    normalized_data_json: dict | None = None
    matched_plan_id: int | None = None
    matched_log_id: int | None = None
    match_status: str
    match_confidence: str | None = None
    suggested_action: str
    user_action: str | None = None
    validation_errors_json: list | None = None
    warnings_json: list | None = None
    field_diff_json: list | None = None
    activity_fingerprint: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkoutImportBatchRead(BaseModel):
    id: int
    status: str
    source_type: str
    source_filename: str | None = None
    merge_strategy: str
    timezone: str
    total_count: int
    matched_plan_count: int
    matched_log_count: int
    unplanned_count: int
    ready_count: int
    conflict_count: int
    invalid_count: int
    skipped_count: int
    client_request_id: str | None = None
    warnings_json: list | None = None
    preview_summary_json: dict | None = None
    expires_at: datetime | None = None
    applied_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[WorkoutImportItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class WorkoutImportCreateResponse(BaseModel):
    batch_id: int
    status: str
    total_count: int
    matched_plan_count: int
    matched_log_count: int
    unplanned_count: int
    ready_count: int
    conflict_count: int
    invalid_count: int
    skipped_count: int
    warnings: list[WorkoutImportIssue] = []
    items: list[WorkoutImportItemRead] = []
    preview_summary: WorkoutImportPreviewSummary


class WorkoutImportApplyResponse(BaseModel):
    batch_id: int
    status: str
    created_count: int = 0
    updated_count: int = 0
    linked_plan_count: int = 0
    unplanned_count: int = 0
    skipped_count: int = 0
    subjective_missing_count: int = 0
