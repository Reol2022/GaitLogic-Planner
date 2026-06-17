from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import AIPlanDraftStatus, AIPlanIntensityStyle, RaceDistance, WorkoutMainTypeNormalized


class AIPlanGenerateRequest(BaseModel):
    runner_level: str = Field(default="intermediate", max_length=64)
    recent_pb_distance: RaceDistance | None = None
    recent_pb_result: str | None = Field(default=None, max_length=64)
    current_weekly_mileage_km: float = Field(..., ge=0, le=300)
    recent_4w_avg_mileage_km: float = Field(..., ge=0, le=300)
    available_training_days_per_week: int = Field(..., ge=1, le=7)
    can_double_run: bool = False
    fixed_rest_days: list[str] = Field(default_factory=list, max_length=7)
    injury_notes: str | None = Field(default=None, max_length=1000)
    training_preferences: str | None = Field(default=None, max_length=1000)
    target_race_name: str | None = Field(default=None, max_length=128)
    target_race_date: date | None = None
    target_distance: RaceDistance
    target_result: str | None = Field(default=None, max_length=64)
    plan_start_date: date
    plan_weeks: int = Field(..., ge=1, le=16)
    intensity_style: AIPlanIntensityStyle = AIPlanIntensityStyle.standard
    include_pace_guidance: bool = True


class AIPlanDraftWorkoutRead(BaseModel):
    id: int | None = None
    workout_date: date
    weekday: str | None = None
    block_name: str | None = None
    phase_name: str | None = None
    planned_content: str
    focus_note: str | None = None
    planned_distance_km: Decimal | None = None
    main_type_raw: str | None = None
    main_type_normalized: WorkoutMainTypeNormalized
    target_pace_text: str | None = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class AIPlanDraftRead(BaseModel):
    id: int
    job_id: int
    title: str
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_race_name: str | None = None
    target_race_date: date | None = None
    target_result: str | None = None
    summary: str | None = None
    risk_notes: list[str] | None = None
    status: AIPlanDraftStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIPlanDraftDetail(AIPlanDraftRead):
    workouts: list[AIPlanDraftWorkoutRead]


class AIPlanGenerateResponse(BaseModel):
    job_id: int
    draft_id: int
    title: str
    goal: str | None = None
    summary: str | None = None
    risk_notes: list[str] | None = None
    workouts: list[AIPlanDraftWorkoutRead]


class AIPlanApplyResponse(BaseModel):
    message: str
    cycle_id: int


class AIPlanQuotaRead(BaseModel):
    model_name: str
    daily_limit: int
    used_count: int
    remaining_count: int
    last_generated_at: datetime | None = None
    cooldown_seconds: int
    can_generate: bool
