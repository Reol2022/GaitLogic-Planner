from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from planner_core.weekly_review.enums import (
    DeviationSeverity,
    DeviationType,
    WeeklyClassificationStatus,
    WeeklyDataQualityLevel,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WeeklyFactsRequest(StrictModel):
    user_id: int = Field(gt=0)
    week_start: date
    week_end: date
    cycle_id: int | None = Field(default=None, gt=0)
    timezone: str = "Asia/Shanghai"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def valid_period(self) -> "WeeklyFactsRequest":
        if self.week_start > self.week_end:
            raise ValueError("week_start must not be after week_end")
        if (self.week_end - self.week_start).days > 6:
            raise ValueError("weekly facts period cannot exceed 7 days")
        return self


class PlannedSessionFact(StrictModel):
    plan_id: int | None = None
    session_date: date
    main_type: str
    distance_km: float | None = Field(default=None, ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    is_cancelled: bool = False


class WorkoutSessionFact(StrictModel):
    log_id: int | None = None
    activity_date: date
    planned_workout_id: int | None = None
    main_type: str = "unknown"
    distance_km: float | None = Field(default=None, ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    status: str
    sport_type: str = "running"
    activity_fingerprint: str | None = None


class RunnerStateSampleFact(StrictModel):
    sample_date: date
    fatigue_state: str = "UNKNOWN"
    load_trend: str = "UNKNOWN"
    recovery_state: str = "UNKNOWN"
    risk_flag_count: int = Field(default=0, ge=0)


class WeeklyPeriod(StrictModel):
    week_start: date
    week_end: date
    timezone: str
    cycle_id: int | None = None
    cycle_name: str | None = None
    training_phase: str | None = None


class WeeklyPlannedMetrics(StrictModel):
    planned_session_count: int
    planned_running_session_count: int
    planned_distance_km: float | None
    planned_duration_minutes: float | None
    planned_key_session_count: int
    planned_high_intensity_session_count: int
    planned_long_run_count: int
    planned_rest_days: int


class WeeklyCompletedMetrics(StrictModel):
    completed_session_count: int
    completed_running_session_count: int
    actual_distance_km: float | None
    actual_duration_minutes: float | None
    completed_key_session_count: int
    completed_high_intensity_session_count: int
    completed_long_run_count: int
    partial_session_count: int
    missed_session_count: int
    extra_session_count: int
    actual_rest_days: int


class WeeklyAdherenceMetrics(StrictModel):
    session_completion_rate: float | None
    distance_completion_rate: float | None
    key_session_completion_rate: float | None
    long_run_completion_rate: float | None


class WeeklyDistributionMetrics(StrictModel):
    easy_distance_km: float | None
    moderate_distance_km: float | None
    hard_distance_km: float | None
    unknown_intensity_distance_km: float | None
    easy_ratio: float | None
    moderate_ratio: float | None
    hard_ratio: float | None


class WeeklyDeviation(StrictModel):
    deviation_type: DeviationType
    date: date
    plan_id: int | None = None
    log_id: int | None = None
    severity: DeviationSeverity
    expected: dict[str, Any] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    evidence_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RunnerStateTrend(StrictModel):
    start_state: dict[str, Any] | None = None
    end_state: dict[str, Any] | None = None
    fatigue_trend: str = "UNKNOWN"
    load_trend: str = "UNKNOWN"
    recovery_trend: str = "UNKNOWN"
    risk_trend: str = "UNKNOWN"
    current_runner_state: str = "UNKNOWN"
    fatigue_level: str = "UNKNOWN"
    sample_count: int = 0


class WeeklyDataQuality(StrictModel):
    level: WeeklyDataQualityLevel
    missing_plan_days: list[date] = Field(default_factory=list)
    missing_log_fields: list[str] = Field(default_factory=list)
    unmatched_log_count: int = 0
    ambiguous_match_count: int = 0
    runner_state_sample_count: int = 0


class WeeklyClassification(StrictModel):
    primary_status: WeeklyClassificationStatus
    secondary_statuses: list[WeeklyClassificationStatus] = Field(default_factory=list)
    rule_codes: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    overall_readiness: str | None = None
    domain_readiness: list[dict[str, object]] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    capability_limitations: list[str] = Field(default_factory=list)


class WeeklyFacts(StrictModel):
    period: WeeklyPeriod
    planned: WeeklyPlannedMetrics
    completed: WeeklyCompletedMetrics
    adherence: WeeklyAdherenceMetrics
    distribution: WeeklyDistributionMetrics
    deviations: list[WeeklyDeviation] = Field(default_factory=list)
    runner_state_trend: RunnerStateTrend
    data_quality: WeeklyDataQuality
    classification: WeeklyClassification
    weekly_facts_version: str
    rules_version: str
    result_hash: str
    generated_at: datetime
