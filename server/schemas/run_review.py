from __future__ import annotations

from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, Field


class RunReviewPlanRead(BaseModel):
    planned_workout_id: int | None = None
    date: Date | None = None
    content: str | None = None
    distance_km: Decimal | None = None
    workout_type: str | None = None


class RunReviewActualRead(BaseModel):
    activity_id: int
    provider: str
    date: Date
    activity_type: str
    distance_km: Decimal | None = None
    duration_seconds: int | None = None
    average_pace_seconds_per_km: int | None = None
    average_heart_rate_bpm: int | None = None
    rpe: int | None = Field(default=None, ge=0, le=10)


class RunReviewRead(BaseModel):
    activity_id: int
    plan: RunReviewPlanRead
    actual: RunReviewActualRead
    distance_delta_km: Decimal | None = None
    distance_delta_percent: Decimal | None = None
    data_quality: str
    limitations: list[str] = Field(default_factory=list)
