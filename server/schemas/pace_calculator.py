from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import PaceZoneCode, RaceDistance


class PaceZoneRead(BaseModel):
    id: int | None = None
    zone_code: PaceZoneCode
    zone_name: str
    pace_min_seconds_per_km: int
    pace_max_seconds_per_km: int
    target_pace_text: str
    description: str | None = None
    sort_order: int | None = None

    model_config = ConfigDict(from_attributes=True)


class PaceCalculationRequest(BaseModel):
    race_distance: RaceDistance
    race_result: str | int = Field(..., examples=["1:12:32"])


class PaceCalculationResponse(BaseModel):
    race_distance: RaceDistance
    race_result_seconds: int
    vdot: float
    zones: list[PaceZoneRead]


class PaceProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    race_distance: RaceDistance
    race_result: str | int = Field(..., examples=["1:12:32"])


class PaceProfileRead(BaseModel):
    id: int
    name: str
    race_distance: RaceDistance
    race_result_seconds: int
    vdot: float
    algorithm_version: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaceProfileDetail(PaceProfileRead):
    zones: list[PaceZoneRead]


class ApplyPaceProfileResponse(BaseModel):
    message: str
    updated_count: int
