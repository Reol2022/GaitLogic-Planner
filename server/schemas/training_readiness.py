from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import ReadinessDataQuality, TrainingStatus


class ReadinessSignal(BaseModel):
    dimension: str
    signal_key: str
    level: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReadinessRecommendation(BaseModel):
    action: str
    message: str
    reason: str
    requires_confirmation: bool = True


class DailyTrainingLoadRead(BaseModel):
    load_date: date
    distance_km: float
    duration_minutes: float
    srpe_load_au: float | None = None
    easy_distance_km: float
    moderate_distance_km: float
    high_intensity_distance_km: float
    key_workout_count: int
    training_session_count: int


class TrainingLoadSummaryRead(BaseModel):
    assessment_date: date
    rolling_7d_distance_km: float
    rolling_7d_duration_minutes: float
    rolling_7d_srpe_load_au: float | None = None
    rolling_7d_high_intensity_distance_km: float
    rolling_7d_key_workout_count: int
    rolling_7d_training_session_count: int
    baseline_28d_total_distance_km: float
    baseline_28d_weekly_distance_km: float
    baseline_28d_total_srpe_load_au: float | None = None
    baseline_28d_weekly_srpe_load_au: float | None = None
    baseline_28d_avg_rpe: float | None = None
    srpe_coverage_ratio: float
    recovery_checkin_coverage_ratio: float
    recent_to_baseline_load_ratio: float | None = None
    load_change_percentage: float | None = None
    distance_change_percentage: float | None = None
    history_days: int
    missing_data: list[str] = Field(default_factory=list)


class TrainingLoadSummaryResponse(BaseModel):
    summary: TrainingLoadSummaryRead


class TrainingLoadDailyResponse(BaseModel):
    items: list[DailyTrainingLoadRead]


class TrainingLoadTrendResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[DailyTrainingLoadRead]


class TrainingReadinessAssessmentRead(BaseModel):
    id: int
    assessment_date: date
    status: TrainingStatus
    data_quality: ReadinessDataQuality
    metrics_json: dict[str, Any]
    external_load_signals_json: list[dict[str, Any]] | None = None
    internal_load_signals_json: list[dict[str, Any]] | None = None
    recovery_signals_json: list[dict[str, Any]] | None = None
    performance_signals_json: list[dict[str, Any]] | None = None
    pain_signals_json: list[dict[str, Any]] | None = None
    reasons_json: list[Any]
    recommendations_json: list[Any]
    missing_data_json: list[Any] | None = None
    algorithm_version: str
    threshold_version: str
    generated_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingReadinessTodayResponse(BaseModel):
    assessment: TrainingReadinessAssessmentRead
    recovery_checkin_completed: bool


class TrainingReadinessHistoryResponse(BaseModel):
    items: list[TrainingReadinessAssessmentRead]
