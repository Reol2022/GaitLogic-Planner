from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdaptiveProposalRead(BaseModel):
    id: int
    week_start: date | None
    status: str
    proposal: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdaptiveApprovalResult(BaseModel):
    proposal_id: int
    status: str
    plan_version_id: int | None = None
    applied_plan_ids: list[int] = Field(default_factory=list)
    duplicate: bool = False


class AdaptivePlanVersionRead(BaseModel):
    id: int
    version_number: int
    previous_version_id: int | None
    rollback_of_version_id: int | None
    proposal_id: int | None
    reason: str
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdaptivePlanVersionList(BaseModel):
    items: list[AdaptivePlanVersionRead]


class PlanRollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class WeeklyGraphRequest(BaseModel):
    week_start: date
    week_end: date
    cycle_id: int | None = Field(default=None, gt=0)
    timezone: str = "Asia/Shanghai"
