from __future__ import annotations

from typing import Protocol

from planner_core.weekly_review.schemas import WeeklyFacts, WeeklyFactsRequest
from server.agent.tools.knowledge_tools import RetrieveTrainingKnowledgeOutput
from planner_core.adaptive_plan.schemas import PlanAdjustmentProposal
from server.weekly_review_graph.schemas import (
    PlanDesignAnalysis,
    WeeklyReviewAnalysis,
    WeeklyReviewDraft,
    WeeklyReviewState,
)


class WeeklyFactsLoader(Protocol):
    def __call__(self, request: WeeklyFactsRequest) -> WeeklyFacts: ...


class WeeklyKnowledgeRetriever(Protocol):
    def __call__(
        self, *, query: str, user_id: int
    ) -> RetrieveTrainingKnowledgeOutput: ...


class WeeklyReviewGenerator(Protocol):
    def __call__(self, state: WeeklyReviewState) -> WeeklyReviewAnalysis | WeeklyReviewDraft: ...


class PlanDesigner(Protocol):
    def __call__(self, state: WeeklyReviewState) -> PlanDesignAnalysis: ...


class ProposalMaterializer(Protocol):
    def __call__(self, state: WeeklyReviewState) -> PlanAdjustmentProposal: ...
