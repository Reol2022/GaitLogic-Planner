from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from planner_core.enums import PlanAdjustmentAction


class ProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdaptiveProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


class PlanValue(ProposalModel):
    content: str = Field(min_length=1, max_length=2000)
    distance_km: float | None = Field(default=None, ge=0)
    main_type: str = Field(min_length=1, max_length=64)
    target_pace_text: str | None = Field(default=None, max_length=255)


class ProposalCandidateChange(ProposalModel):
    plan_id: int = Field(gt=0)
    action: PlanAdjustmentAction
    after: PlanValue
    reason: str = Field(min_length=1, max_length=1000)
    rule_evidence: list[str] = Field(min_length=1, max_length=20)


class PlanAdjustmentChange(ProposalModel):
    date: date
    plan_id: int = Field(gt=0)
    action: PlanAdjustmentAction
    before: PlanValue
    after: PlanValue
    reason: str = Field(min_length=1, max_length=1000)
    rule_evidence: list[str] = Field(min_length=1, max_length=20)


class PlanAdjustmentProposal(ProposalModel):
    proposal_id: UUID = Field(default_factory=uuid4)
    user_id: int = Field(gt=0, exclude=True)
    week_start: date
    week_end: date
    status: AdaptiveProposalStatus = AdaptiveProposalStatus.PENDING_APPROVAL
    reason_codes: list[str] = Field(default_factory=list, max_length=30)
    changes: list[PlanAdjustmentChange] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    created_at: datetime

    @model_validator(mode="after")
    def validate_period_and_unique_plans(self) -> "PlanAdjustmentProposal":
        if self.week_start > self.week_end:
            raise ValueError("week_start must not be after week_end")
        ids = [item.plan_id for item in self.changes]
        if len(ids) != len(set(ids)):
            raise ValueError("a plan may only appear once in a proposal")
        return self


class TargetPlanFact(ProposalModel):
    plan_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    workout_date: date
    value: PlanValue
    is_locked: bool = False
    is_completed: bool = False
