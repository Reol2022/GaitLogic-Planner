from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class UnknownState(str, Enum):
    UNKNOWN = "UNKNOWN"


class DataQualityLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RunnerIdentityReference(BaseModel):
    runner_id: int
    generated_at: datetime
    timezone: str
    calculation_window_end: date
    calculation_window_start_7d: date
    calculation_window_start_28d: date


class RunnerGoalContext(BaseModel):
    race_distance: str | None = None
    race_date: date | None = None
    target_time_seconds: int | None = None
    weeks_remaining: float | None = None


class RecentTrainingMetrics(BaseModel):
    distance_7d_km: float | None = None
    distance_28d_km: float | None = None
    duration_7d_minutes: float | None = None
    duration_28d_minutes: float | None = None
    sessions_7d: int = 0
    sessions_28d: int = 0
    completed_sessions_7d: int = 0
    completed_sessions_28d: int = 0
    planned_sessions_7d: int = 0
    planned_sessions_28d: int = 0
    completion_rate_7d: float | None = None
    completion_rate_28d: float | None = None
    average_rpe_7d: float | None = None
    average_rpe_28d: float | None = None


class IntensityMetrics(BaseModel):
    easy_distance_7d_km: float | None = None
    moderate_distance_7d_km: float | None = None
    hard_distance_7d_km: float | None = None
    easy_distance_28d_km: float | None = None
    moderate_distance_28d_km: float | None = None
    hard_distance_28d_km: float | None = None
    hard_distance_ratio_7d: float | None = None
    hard_distance_ratio_28d: float | None = None
    quality_sessions_7d: int = 0
    quality_sessions_28d: int = 0
    long_run_distance_7d_km: float | None = None
    long_run_distance_28d_km: float | None = None
    days_since_last_quality_session: int | None = None


class InferredStatePlaceholders(BaseModel):
    fitness_state: UnknownState = UnknownState.UNKNOWN
    fatigue_state: UnknownState = UnknownState.UNKNOWN
    load_trend: UnknownState = UnknownState.UNKNOWN
    training_consistency: UnknownState = UnknownState.UNKNOWN
    training_phase: UnknownState = UnknownState.UNKNOWN
    weaknesses: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class RunnerStateDataQuality(BaseModel):
    data_quality_level: DataQualityLevel
    confidence: float = Field(ge=0, le=1)
    available_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    valid_workout_count_7d: int = 0
    valid_workout_count_28d: int = 0
    rpe_coverage_7d: float = Field(default=0, ge=0, le=1)
    rpe_coverage_28d: float = Field(default=0, ge=0, le=1)
    heart_rate_coverage_7d: float = Field(default=0, ge=0, le=1)
    heart_rate_coverage_28d: float = Field(default=0, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class RunnerStateSnapshot(BaseModel):
    identity: RunnerIdentityReference
    goal_context: RunnerGoalContext
    recent_training: RecentTrainingMetrics
    intensity: IntensityMetrics
    inferred_state: InferredStatePlaceholders
    data_quality: RunnerStateDataQuality


class RunnerStateCurrentResponse(BaseModel):
    snapshot: RunnerStateSnapshot
