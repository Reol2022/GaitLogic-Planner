from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from planner_core.enums import AIPlanDraftStatus, AIPlanIntensityStyle, RaceDistance, WorkoutMainTypeNormalized

WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
PLAN_TYPES = {'REC', 'E', 'LSD', 'M', 'T1', 'T2', 'I', 'R', 'Mixed'}


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
    daily_available_minutes: dict[str, int] = Field(default_factory=dict, max_length=7)
    long_run_preferred_day: str | None = None
    excluded_workout_types: list[str] = Field(default_factory=list, max_length=10)
    use_training_context: bool = True

    @field_validator('fixed_rest_days')
    @classmethod
    def valid_rest_days(cls, value):
        if any(day not in WEEKDAYS for day in value):
            raise ValueError('休息日必须为周一至周日')
        return list(dict.fromkeys(value))

    @field_validator('daily_available_minutes')
    @classmethod
    def valid_daily_minutes(cls, value):
        if any(day not in WEEKDAYS or minutes < 0 or minutes > 600 for day, minutes in value.items()):
            raise ValueError('每日可用时间必须为周一至周日、0至600分钟')
        return value

    @field_validator('long_run_preferred_day')
    @classmethod
    def valid_long_day(cls, value):
        if value is not None and value not in WEEKDAYS:
            raise ValueError('长距离偏好日必须为周一至周日')
        return value

    @field_validator('excluded_workout_types')
    @classmethod
    def valid_excluded_types(cls, value):
        if any(item not in PLAN_TYPES for item in value):
            raise ValueError('不支持的禁用训练类型')
        return list(dict.fromkeys(value))


class PlanContextIssue(BaseModel):
    code: str
    message: str
    severity: str = 'warning'


class PlanContextRead(BaseModel):
    schema_version: str = '2.0'
    as_of_date: date
    timezone: str
    runner_facts: dict
    hard_constraints: dict = Field(default_factory=dict)
    soft_preferences: dict = Field(default_factory=dict)
    user_reported: dict = Field(default_factory=dict)
    feasibility: list[PlanContextIssue] = Field(default_factory=list)
    suggestions: dict[str, float] = Field(default_factory=dict)
    fingerprint: str = ''


class AIPlanApplyRequest(BaseModel):
    activate: bool = False


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
    plan_context: PlanContextRead | None = None


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
    cycle_status: str = 'draft'
    activated: bool = False


class AIPlanQuotaRead(BaseModel):
    model_name: str
    daily_limit: int
    used_count: int
    remaining_count: int
    last_generated_at: datetime | None = None
    cooldown_seconds: int
    can_generate: bool
