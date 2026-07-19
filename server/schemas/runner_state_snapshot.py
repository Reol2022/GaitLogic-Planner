from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from planner_core.enums import RunnerStateSnapshotTriggerType


class RunnerStateSnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunnerStateSnapshotListItem(BaseModel):
    id: int
    snapshot_date: date
    data_cutoff_date: date
    calculated_at: datetime
    created_at: datetime
    trigger_type: RunnerStateSnapshotTriggerType
    snapshot_schema_version: str
    ruleset_version: str
    distance_7d_km: float | None = None
    distance_28d_km: float | None = None
    volume_trend: str | None = None
    training_consistency: str | None = None
    fatigue_state: str | None = None
    training_phase: str | None = None
    risk_flag_count: int
    evidence_coverage: float | None = Field(default=None, ge=0, le=1)
    data_completeness: float | None = Field(default=None, ge=0, le=1)


class RunnerStateSnapshotDetail(RunnerStateSnapshotListItem):
    snapshot_payload: dict[str, Any]


class RunnerStateSnapshotCreateResult(BaseModel):
    snapshot: RunnerStateSnapshotDetail
    created: bool
    duplicate: bool


class RunnerStateSnapshotListResponse(BaseModel):
    items: list[RunnerStateSnapshotListItem]
    total: int
    limit: int
    offset: int
