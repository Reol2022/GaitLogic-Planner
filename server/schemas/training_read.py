from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RecentTrainingSessionRead(BaseModel):
    date: date
    planned_date: date | None = None
    training_type: str
    classification_basis: str = "ACTUAL_LOG"
    association_status: str = "UNPLANNED"
    planned_or_unplanned: str
    completion_status: str
    distance_km: float | None = None
    duration_seconds: int | None = None
    average_pace_seconds_per_km: int | None = None
    average_heart_rate: int | None = None
    rpe: int | None = None
    source: str
    brief_review: str | None = Field(default=None, max_length=240)
    is_key_session: bool = False


class RecentTrainingRead(BaseModel):
    as_of_date: date
    start_date: date | None = None
    end_date: date | None = None
    window_days: int
    items: list[RecentTrainingSessionRead]
    total_sessions: int
    total_distance_km: float | None = None
    completed_key_sessions: int
    rest_days: int
    planned_sessions_due: int = 0
    completed_planned_sessions: int = 0
    unplanned_sessions: int = 0
    completion_rate: float | None = None
    unresolved_activity_count: int = 0
    duplicate_candidate_count: int = 0
    cross_date_association_count: int = 0


class TrainingDataQualityRead(BaseModel):
    as_of_date: date
    window_days: int
    valid_workout_count: int
    coverage: dict[str, float]
    missing_fields: list[str]
    source_mix: dict[str, int]
    freshness_days: int | None = None

