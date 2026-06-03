from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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


class TrainingCycleRead(TrainingCycleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

