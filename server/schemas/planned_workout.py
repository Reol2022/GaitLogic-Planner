from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from planner_core.enums import WorkoutMainTypeNormalized
from server.schemas.workout_log import WorkoutLogRead


class PlannedWorkoutBase(BaseModel):
    cycle_id: int
    block_id: int
    workout_date: date | None = None
    date_text: str | None = None
    weekday: str | None = None
    month_text: str | None = None
    phase_name: str | None = None
    planned_content: str
    focus_note: str | None = None
    target_pace_text: str | None = None
    planned_distance_km: Decimal | None = None
    main_type_raw: str | None = None
    main_type_normalized: WorkoutMainTypeNormalized = WorkoutMainTypeNormalized.unknown
    source_sheet: str | None = None
    source_row: int | None = None
    sort_order: int


class PlannedWorkoutCreate(PlannedWorkoutBase):
    pass


class PlannedWorkoutUpdate(BaseModel):
    cycle_id: int | None = None
    block_id: int | None = None
    workout_date: date | None = None
    date_text: str | None = None
    weekday: str | None = None
    month_text: str | None = None
    phase_name: str | None = None
    planned_content: str | None = None
    focus_note: str | None = None
    target_pace_text: str | None = None
    planned_distance_km: Decimal | None = None
    main_type_raw: str | None = None
    main_type_normalized: WorkoutMainTypeNormalized | None = None
    source_sheet: str | None = None
    source_row: int | None = None
    sort_order: int | None = None


class PlannedWorkoutRead(PlannedWorkoutBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlannedWorkoutWithLogRead(PlannedWorkoutRead):
    workout_log: WorkoutLogRead | None = None
