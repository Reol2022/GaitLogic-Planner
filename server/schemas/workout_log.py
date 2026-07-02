from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import PainScaleVersion, WorkoutStatusNormalized


class WorkoutLogBase(BaseModel):
    status_raw: str | None = None
    status_normalized: WorkoutStatusNormalized = WorkoutStatusNormalized.not_started
    actual_distance_km: Decimal | None = None
    actual_duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    elapsed_time_seconds: int | None = None
    avg_pace_seconds_per_km: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    average_cadence_spm: int | None = None
    max_cadence_spm: int | None = None
    elevation_gain_m: int | None = None
    calories_kcal: int | None = None
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
    pain_level: int | None = Field(default=None, ge=0, le=10)
    pain_scale_version: PainScaleVersion = PainScaleVersion.native_0_10
    main_session_data: str | None = None
    review_note: str | None = None
    tomorrow_adjustment: str | None = None
    alert_message: str | None = None
    completion_rate: Decimal | None = None
    activity_date: date | None = None
    start_time: time | None = None
    timezone: str | None = None
    session_index: int = 1
    sport_type: str = "running"
    workout_type: str | None = None
    title: str | None = None
    is_unplanned: bool = False
    source_type: str = "manual"
    source_import_batch_id: int | None = None
    external_activity_id: str | None = None
    activity_fingerprint: str | None = None
    field_sources_json: dict | None = None


class WorkoutLogUpdate(BaseModel):
    status_raw: str | None = None
    status_normalized: WorkoutStatusNormalized | None = None
    actual_distance_km: Decimal | None = None
    actual_duration_seconds: int | None = None
    moving_time_seconds: int | None = None
    elapsed_time_seconds: int | None = None
    avg_pace_seconds_per_km: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    average_cadence_spm: int | None = None
    max_cadence_spm: int | None = None
    elevation_gain_m: int | None = None
    calories_kcal: int | None = None
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
    pain_level: int | None = Field(default=None, ge=0, le=10)
    pain_scale_version: PainScaleVersion | None = None
    main_session_data: str | None = None
    review_note: str | None = None
    tomorrow_adjustment: str | None = None
    alert_message: str | None = None
    completion_rate: Decimal | None = None
    activity_date: date | None = None
    start_time: time | None = None
    timezone: str | None = None
    session_index: int | None = None
    sport_type: str | None = None
    workout_type: str | None = None
    title: str | None = None


class WorkoutLogRead(WorkoutLogBase):
    id: int
    planned_workout_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
