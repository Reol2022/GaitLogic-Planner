"""Adapter exposing the existing WeeklyReviewGraph as a Coach Skill."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from planner_core.weekly_review.schemas import WeeklyFactsRequest
from server.agent.gateway import AgentLLMGateway
from server.agent.schemas import AgentContext
from server.agent.skill import SkillResult, SkillStatus
from server.agent.skills import WeeklyReviewSkillInput
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.agent.tools.knowledge_tools import build_configured_knowledge_tool
from server.observability.tracing import SafeTracer
from server.services.weekly_facts_service import WeeklyFactsService
from server.weekly_review_graph.adapters import AgentGatewayWeeklyReviewGenerator, KnowledgeToolWeeklyRetriever, RegistryWeeklyEvidenceReacquirer
from server.weekly_review_graph.schemas import WeeklyReviewState
from server.weekly_review_graph.workflow import build_weekly_review_graph


def build_weekly_review_skill_runner(*, db: Session, gateway: AgentLLMGateway, settings, tracer: SafeTracer):
    facts_service = WeeklyFactsService()
    knowledge_tool = build_configured_knowledge_tool(settings)

    def run(arguments: WeeklyReviewSkillInput, context: AgentContext) -> SkillResult:
        week_end = arguments.week_end or context.current_time.date()
        week_start = arguments.week_start or week_end - timedelta(days=6)
        request = WeeklyFactsRequest(user_id=context.user_id, week_start=week_start, week_end=week_end, timezone=context.timezone)
        evidence_registry = build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db), knowledge_tool=knowledge_tool)
        graph = build_weekly_review_graph(
            facts_loader=lambda item: facts_service.build_weekly_facts(db, item),
            generator=AgentGatewayWeeklyReviewGenerator(gateway),
            knowledge_retriever=KnowledgeToolWeeklyRetriever(knowledge_tool, timezone=context.timezone) if knowledge_tool else None,
            evidence_reacquirer=RegistryWeeklyEvidenceReacquirer(evidence_registry, timezone=context.timezone),
            max_reflect_rounds=settings.evidence_max_reflect_rounds, tracer=tracer,
        )
        state = WeeklyReviewState.model_validate(graph.invoke(WeeklyReviewState(user_id=context.user_id, request=request).model_dump(mode="python")))
        if state.final_review is None:
            return SkillResult(skill_name="weekly_review", status=SkillStatus.FAILED, summary="Weekly Review workflow did not return a review.")
        review = state.final_review
        return SkillResult(skill_name="weekly_review", status=SkillStatus.PARTIAL if review.fallback_used else SkillStatus.SUCCESS,
            summary=review.overview, facts={"week_start": str(week_start), "week_end": str(week_end), "evidence_status": review.evidence_status},
            evidence_refs=[item.model_dump(mode="json") for item in review.knowledge_references],
            warnings=[{"code": "WEEKLY_REVIEW_WARNING", "message": item} for item in review.warnings])
    return run
