from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from server.domain.decision_readiness import DecisionReadiness
from server.schemas.training_rules import TrainingRuleEvaluateResponse


class RuleLoopSummary(BaseModel):
    blocking: int = 0
    high: int = 0
    caution: int = 0
    notice: int = 0
    info: int = 0


class RuleLoopEvaluationResponse(BaseModel):
    validation_status: str
    title: str
    message: str
    data_limited: bool = False
    decision_readiness: DecisionReadiness = DecisionReadiness.READY
    data_limitations: list[str] = Field(default_factory=list)
    summary: RuleLoopSummary
    evaluation: TrainingRuleEvaluateResponse
    facts_hash: str | None = None
    generated_adjustment_draft_id: int | None = None
    evaluated_at: datetime | None = None


class PlanValidationRequest(BaseModel):
    cycle_id: int
    force: bool = False


class DraftValidationRequest(BaseModel):
    force: bool = False


class TodayEvaluationResponse(RuleLoopEvaluationResponse):
    pass


class TrainingAdjustmentDraftRead(BaseModel):
    id: int
    user_id: int
    source_type: str
    source_evaluation_id: int | None = None
    cycle_id: int | None = None
    week_start: date | None = None
    status: str
    adjustment_json: dict[str, Any]
    explanation_json: dict[str, Any]
    original_plan_snapshot_json: dict[str, Any]
    applied_result_json: dict[str, Any] | None = None
    facts_hash: str | None = None
    source_version: str | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingAdjustmentDraftListResponse(BaseModel):
    items: list[TrainingAdjustmentDraftRead]
    total: int
    limit: int
    offset: int


class TrainingAdjustmentApplyResponse(BaseModel):
    draft_id: int
    status: str
    applied_result: dict[str, Any]
