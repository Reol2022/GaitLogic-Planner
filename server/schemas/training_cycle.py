from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from planner_core.enums import TrainingCycleStatus


class TrainingCycleBase(BaseModel):
    name: str
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_race_name: str | None = None
    target_race_date: date | None = None
    target_result: str | None = None
    description: str | None = None


class TrainingCycleCreate(TrainingCycleBase):
    pass


class TrainingCycleUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_race_name: str | None = None
    target_race_date: date | None = None
    target_result: str | None = None
    description: str | None = None


class TrainingCycleActivateRequest(BaseModel):
    effective_start_date: date
    complete_current_cycle: bool = True


class TrainingCycleCompleteRequest(BaseModel):
    actual_end_date: date | None = None


class TrainingCycleActivationPreview(BaseModel):
    current_cycle_id: int | None = None
    current_cycle_name: str | None = None
    new_cycle_id: int
    new_cycle_name: str
    effective_start_date: date
    current_cycle_actual_end_date: date | None = None
    future_uncompleted_plan_count: int = 0
    completed_logs_preserved: bool = True


class TrainingCycleRead(TrainingCycleBase):
    id: int
    status: TrainingCycleStatus = TrainingCycleStatus.draft
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    activated_at: datetime | None = None
    completed_at: datetime | None = None
    superseded_by_cycle_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
