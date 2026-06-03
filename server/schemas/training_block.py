from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from planner_core.enums import BlockType


class TrainingBlockBase(BaseModel):
    cycle_id: int
    block_name: str
    block_type: BlockType = BlockType.week
    week_index: int | None = None
    sort_order: int
    date_range_text: str | None = None
    target_text: str | None = None
    target_distance_min_km: Decimal | None = None
    target_distance_max_km: Decimal | None = None
    planned_distance_km: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    phase_name: str | None = None
    focus: str | None = None


class TrainingBlockCreate(TrainingBlockBase):
    pass


class TrainingBlockUpdate(BaseModel):
    cycle_id: int | None = None
    block_name: str | None = None
    block_type: BlockType | None = None
    week_index: int | None = None
    sort_order: int | None = None
    date_range_text: str | None = None
    target_text: str | None = None
    target_distance_min_km: Decimal | None = None
    target_distance_max_km: Decimal | None = None
    planned_distance_km: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    phase_name: str | None = None
    focus: str | None = None


class TrainingBlockRead(TrainingBlockBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

