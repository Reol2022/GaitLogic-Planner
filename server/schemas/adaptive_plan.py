from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdaptiveProposalRead(BaseModel):
    id: int
    week_start: date | None
    status: str
    proposal: dict[str, Any]
    review_report_id: int | None = None
    revision: int = 1
    parent_proposal_id: int | None = None
    feedback: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdaptiveApprovalResult(BaseModel):
    proposal_id: int
    status: str
    plan_version_id: int | None = None
    applied_plan_ids: list[int] = Field(default_factory=list)
    duplicate: bool = False


class ProposalFeedbackReason(str, Enum):
    volume_too_high = "VOLUME_TOO_HIGH"
    volume_too_low = "VOLUME_TOO_LOW"
    too_many_quality_sessions = "TOO_MANY_QUALITY_SESSIONS"
    workout_day_conflict = "WORKOUT_DAY_CONFLICT"
    long_run_conflict = "LONG_RUN_CONFLICT"
    insufficient_recovery = "INSUFFICIENT_RECOVERY"
    personal_schedule_conflict = "PERSONAL_SCHEDULE_CONFLICT"
    other = "OTHER"


class ProposalRevisionFeedback(BaseModel):
    reason_codes: list[ProposalFeedbackReason] = Field(default_factory=list, max_length=8)
    free_text: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_meaningful_feedback(self) -> "ProposalRevisionFeedback":
        if not self.reason_codes and not (self.free_text or "").strip():
            raise ValueError("reason_codes or free_text is required")
        return self


class ProposalRevisionRequest(BaseModel):
    proposal_id: int = Field(gt=0)
    feedback: ProposalRevisionFeedback
    decision: Literal["REGENERATE_WITH_FEEDBACK"] = "REGENERATE_WITH_FEEDBACK"


class ProposalRevisionResult(BaseModel):
    status: Literal["PENDING_APPROVAL", "REVIEW_STALE", "REVISION_LIMIT_REACHED"]
    proposal: AdaptiveProposalRead | None = None
    revision_limit: int = Field(ge=0)


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
    source_block_id: int | None = Field(default=None, gt=0)
    target_block_id: int | None = Field(default=None, gt=0)
    timezone: str = "Asia/Shanghai"
