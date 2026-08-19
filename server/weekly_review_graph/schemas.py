from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.weekly_review.schemas import WeeklyFacts, WeeklyFactsRequest
from server.agent.schemas import AgentKnowledgeReference
from server.agent.tools.knowledge_tools import KnowledgeToolResultItem
from planner_core.adaptive_plan.schemas import (
    PlanAdjustmentProposal,
    ProposalCandidateChange,
    TargetPlanFact,
)


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WeeklyReviewGraphStatus(str, Enum):
    PENDING = "PENDING"
    FACTS_READY = "FACTS_READY"
    RULES_READY = "RULES_READY"
    KNOWLEDGE_READY = "KNOWLEDGE_READY"
    DRAFT_READY = "DRAFT_READY"
    ANALYSIS_READY = "ANALYSIS_READY"
    PLAN_DESIGN_READY = "PLAN_DESIGN_READY"
    PROPOSAL_READY = "PROPOSAL_READY"
    VALIDATED = "VALIDATED"
    FALLBACK = "FALLBACK"
    COMPLETED = "COMPLETED"


class WeeklyReviewDraft(GraphModel):
    overview: str = Field(min_length=1, max_length=2000)
    completion_summary: str = Field(min_length=1, max_length=2000)
    key_session_summary: str = Field(min_length=1, max_length=2000)
    deviation_summary: str = Field(min_length=1, max_length=2000)
    fatigue_and_risk: str = Field(min_length=1, max_length=2000)
    next_week_focus: list[str] = Field(default_factory=list, max_length=8)
    knowledge_reference_ids: list[str] = Field(default_factory=list, max_length=6)


class WeeklyReviewAnalysis(GraphModel):
    overall_assessment: str = Field(min_length=1, max_length=3000)
    execution_assessment: str = Field(min_length=1, max_length=3000)
    load_assessment: str = Field(min_length=1, max_length=3000)
    key_session_assessment: str = Field(min_length=1, max_length=3000)
    recovery_assessment: str = Field(min_length=1, max_length=3000)
    intensity_assessment: str = Field(min_length=1, max_length=3000)
    positive_signals: list[str] = Field(default_factory=list, max_length=12)
    risk_signals: list[str] = Field(default_factory=list, max_length=12)
    next_week_constraints: list[str] = Field(default_factory=list, max_length=12)
    recommended_direction: list[str] = Field(default_factory=list, max_length=8)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    knowledge_reference_ids: list[str] = Field(default_factory=list, max_length=6)


class PlanDesignAnalysis(GraphModel):
    volume_direction: Literal["reduce", "maintain", "progress"]
    intensity_direction: Literal["reduce", "maintain", "progress"]
    quality_session_count: int = Field(ge=0, le=4)
    key_session_strategy: str = Field(min_length=1, max_length=3000)
    long_run_strategy: str = Field(min_length=1, max_length=3000)
    recovery_spacing: str = Field(min_length=1, max_length=3000)
    candidate_adjustments: list[ProposalCandidateChange] = Field(default_factory=list, max_length=20)
    reason_summary: str = Field(min_length=1, max_length=3000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class WeeklyReviewResult(GraphModel):
    weekly_facts: WeeklyFacts
    rule_results: list[str]
    overview: str
    completion_summary: str
    key_session_summary: str
    deviation_summary: str
    fatigue_and_risk: str
    next_week_focus: list[str]
    warnings: list[str]
    limitations: list[str]
    knowledge_references: list[AgentKnowledgeReference]
    fallback_used: bool
    proposal_record_id: int | None = None


class WeeklyReviewState(GraphModel):
    user_id: int = Field(gt=0)
    request: WeeklyFactsRequest
    weekly_facts: WeeklyFacts | None = None
    rule_results: list[str] = Field(default_factory=list)
    knowledge_results: list[KnowledgeToolResultItem] = Field(default_factory=list)
    knowledge_reference_ids: list[str] = Field(default_factory=list)
    target_plans: list[TargetPlanFact] = Field(default_factory=list, max_length=30)
    review_draft: WeeklyReviewDraft | None = None
    weekly_analysis: WeeklyReviewAnalysis | None = None
    plan_design: PlanDesignAnalysis | None = None
    proposal: PlanAdjustmentProposal | None = None
    validated_review: WeeklyReviewDraft | None = None
    final_review: WeeklyReviewResult | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace_context: dict[str, Any] = Field(default_factory=dict)
    status: WeeklyReviewGraphStatus = WeeklyReviewGraphStatus.PENDING
    validation_errors: list[str] = Field(default_factory=list)
