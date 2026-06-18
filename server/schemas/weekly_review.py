from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from planner_core.enums import (
    PlanAdjustmentAction,
    PlanAdjustmentDraftStatus,
    TrainingStatus,
    WeeklyReviewStatus,
    WorkoutMainTypeNormalized,
)


class WeeklyReviewMetrics(BaseModel):
    week_start_date: date
    week_end_date: date
    is_week_complete: bool
    planned_distance_km: float
    actual_distance_km: float
    completion_rate: float
    planned_workout_days: int
    completed_workout_days: int
    completed_high_count: int
    completed_normal_count: int
    completed_adjusted_count: int
    missed_count: int
    rest_count: int
    skipped_count: int
    avg_rpe: float | None = None
    key_workout_avg_rpe: float | None = None
    max_pain_level: int | None = None
    planned_type_distance: dict[str, float] = Field(default_factory=dict)
    actual_type_distance: dict[str, float] = Field(default_factory=dict)
    key_workouts: list[dict[str, Any]] = Field(default_factory=list)
    long_run: dict[str, Any] | None = None
    recent_7d_distance_km: float
    recent_28d_weekly_avg_km: float
    load_change_percentage: float | None = None
    consecutive_high_intensity_days: list[list[str]] = Field(default_factory=list)
    logged_workout_ratio: float
    valid_log_count: int
    avg_sleep_hours: float | None = None
    avg_hrv: float | None = None
    avg_morning_heart_rate: float | None = None
    missing_fields: list[str] = Field(default_factory=list)
    daily_workouts: list[dict[str, Any]] = Field(default_factory=list)


class TrainingStatusResult(BaseModel):
    status: TrainingStatus
    reasons: list[str] = Field(default_factory=list)
    signals: list[dict[str, str]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)


class WeeklyReviewGenerateRequest(BaseModel):
    cycle_id: int
    source_block_id: int
    target_block_id: int | None = None
    force_regenerate: bool = False


class WeeklyReviewAIAdjustment(BaseModel):
    planned_workout_id: int
    action: PlanAdjustmentAction
    suggested_content: str = Field(min_length=1, max_length=4000)
    suggested_distance_km: float = Field(ge=0, le=500)
    suggested_main_type: WorkoutMainTypeNormalized
    suggested_target_pace_text: str | None = Field(default=None, max_length=255)
    reason: str = Field(min_length=1, max_length=2000)


class WeeklyReviewAIOutput(BaseModel):
    summary: str = Field(min_length=1)
    positive_points: list[str]
    attention_points: list[str]
    training_status: TrainingStatus
    status_explanation: str = Field(min_length=1)
    next_week_strategy: str = Field(min_length=1)
    adjustments: list[WeeklyReviewAIAdjustment]
    risk_notes: list[str]

    model_config = ConfigDict(extra="forbid")


class PlanAdjustmentItemUpdate(BaseModel):
    is_selected: bool | None = None
    suggested_content: str | None = Field(default=None, min_length=1, max_length=4000)
    suggested_distance_km: float | None = Field(default=None, ge=0, le=500)
    suggested_main_type: WorkoutMainTypeNormalized | None = None
    suggested_target_pace_text: str | None = Field(default=None, max_length=255)


class PlanAdjustmentApplyRequest(BaseModel):
    selected_item_ids: list[int] = Field(default_factory=list)

    @field_validator("selected_item_ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("selected_item_ids must not contain duplicates")
        return value


class PlanAdjustmentItemRead(BaseModel):
    id: int
    draft_id: int
    planned_workout_id: int
    workout_date: date | None = None
    action: PlanAdjustmentAction
    original_content: str
    suggested_content: str
    original_distance_km: float | None = None
    suggested_distance_km: float | None = None
    original_main_type: str | None = None
    suggested_main_type: str | None = None
    original_target_pace_text: str | None = None
    suggested_target_pace_text: str | None = None
    reason: str
    is_selected: bool
    is_applied: bool
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanAdjustmentDraftRead(BaseModel):
    id: int
    review_report_id: int
    cycle_id: int
    source_block_id: int
    target_block_id: int
    status: PlanAdjustmentDraftStatus
    summary: str | None = None
    original_week_distance_km: float | None = None
    suggested_week_distance_km: float | None = None
    applied_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[PlanAdjustmentItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class WeeklyReviewReportRead(BaseModel):
    id: int
    cycle_id: int
    source_block_id: int
    target_block_id: int | None = None
    week_start_date: date
    week_end_date: date
    version: int
    status: WeeklyReviewStatus
    training_status: TrainingStatus
    metrics_json: dict[str, Any]
    rule_reasons_json: list[str] | None = None
    missing_data_json: list[str] | None = None
    summary: str | None = None
    positive_points_json: list[str] | None = None
    attention_points_json: list[str] | None = None
    next_week_strategy: str | None = None
    risk_notes_json: list[str] | None = None
    algorithm_version: str
    prompt_version: str | None = None
    model_name: str | None = None
    error_message: str | None = None
    generated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyReviewSummaryResponse(BaseModel):
    metrics: WeeklyReviewMetrics
    training_status: TrainingStatusResult


class WeeklyReviewDetailResponse(BaseModel):
    report: WeeklyReviewReportRead
    adjustment_draft: PlanAdjustmentDraftRead | None = None


class WeeklyReviewListResponse(BaseModel):
    items: list[WeeklyReviewReportRead]
    total: int
    page: int
    page_size: int


class PlanAdjustmentApplyResponse(BaseModel):
    draft_id: int
    status: PlanAdjustmentDraftStatus
    applied_item_ids: list[int]
    before: list[dict[str, Any]]
    after: list[dict[str, Any]]
