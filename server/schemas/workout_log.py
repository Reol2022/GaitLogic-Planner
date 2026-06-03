from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import WorkoutStatusNormalized


class WorkoutLogBase(BaseModel):
    status_raw: str | None = None
    status_normalized: WorkoutStatusNormalized = WorkoutStatusNormalized.not_started
    actual_distance_km: Decimal | None = None
    actual_duration_seconds: int | None = None
    avg_pace_seconds_per_km: int | None = None
    avg_heart_rate: int | None = None
    rpe: int | None = None
    i_effective_km: Decimal | None = None
    t1_effective_km: Decimal | None = None
    t2_effective_km: Decimal | None = None
    m_effective_km: Decimal | None = None
    r_effective_km: Decimal | None = None
    sleep_hours: Decimal | None = None
    hrv: int | None = None
    morning_heart_rate: int | None = None
    weight_kg: Decimal | None = None
    leg_feeling: str | None = None
    pain_location: str | None = None
    pain_level: int | None = Field(default=None, ge=0, le=5)
    main_session_data: str | None = None
    review_note: str | None = None
    tomorrow_adjustment: str | None = None
    alert_message: str | None = None
    completion_rate: Decimal | None = None


class WorkoutLogUpdate(BaseModel):
    status_raw: str | None = None
    status_normalized: WorkoutStatusNormalized | None = None
    actual_distance_km: Decimal | None = None
    actual_duration_seconds: int | None = None
    avg_pace_seconds_per_km: int | None = None
    avg_heart_rate: int | None = None
    rpe: int | None = None
    i_effective_km: Decimal | None = None
    t1_effective_km: Decimal | None = None
    t2_effective_km: Decimal | None = None
    m_effective_km: Decimal | None = None
    r_effective_km: Decimal | None = None
    sleep_hours: Decimal | None = None
    hrv: int | None = None
    morning_heart_rate: int | None = None
    weight_kg: Decimal | None = None
    leg_feeling: str | None = None
    pain_location: str | None = None
    pain_level: int | None = Field(default=None, ge=0, le=5)
    main_session_data: str | None = None
    review_note: str | None = None
    tomorrow_adjustment: str | None = None
    alert_message: str | None = None
    completion_rate: Decimal | None = None


class WorkoutLogRead(WorkoutLogBase):
    id: int
    planned_workout_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

