from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized


class TrainingCalendarDayRead(BaseModel):
    date: date
    weekday: str
    planned_workout_id: int | None = None
    planned_content: str | None = None
    planned_distance_km: Decimal | None = None
    main_type: WorkoutMainTypeNormalized | None = None
    status_normalized: WorkoutStatusNormalized
    actual_distance_km: Decimal | None = None
    avg_pace_seconds_per_km: int | None = None
    avg_heart_rate: int | None = None
    rpe: int | None = None
    review_note: str | None = None
    completion_rate: Decimal | None = None
    source_type: str | None = None
    subjective_status: str | None = None
    has_garmin_activity: bool = False


class TrainingCalendarSummaryRead(BaseModel):
    planned_distance_km: Decimal
    actual_distance_km: Decimal
    completion_rate: Decimal
    completed_days: int
    missed_days: int


class TrainingCalendarRead(BaseModel):
    month: str
    days: list[TrainingCalendarDayRead]
    summary: TrainingCalendarSummaryRead
