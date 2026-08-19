from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.gateway import AgentLLMGateway
from server.agent.schemas import AgentContext, AgentToolResult
from server.agent.tools.knowledge_tools import (
    RetrieveTrainingKnowledgeInput,
    RetrieveTrainingKnowledgeOutput,
    RetrieveTrainingKnowledgeTool,
)
from server.agent.trace import AgentTrace
from server.weekly_review_graph.schemas import WeeklyReviewDraft, WeeklyReviewState
from planner_core.config import Settings
from sqlalchemy.orm import Session
from server.model_tasks import ModelTaskType, task_model_profile
from server.services.adaptive_plan_proposal_service import AdaptivePlanProposalService
from server.services.provider_reasoning_service import persist_reasoning
from server.structured_task_provider import StructuredTaskProvider
from server.weekly_review_graph.schemas import PlanDesignAnalysis, WeeklyReviewAnalysis


class AgentGatewayWeeklyReviewGenerator:
    def __init__(self, gateway: AgentLLMGateway) -> None:
        self.gateway = gateway

    def __call__(self, state: WeeklyReviewState) -> WeeklyReviewDraft:
        if state.weekly_facts is None:
            raise ValueError("Weekly facts are required")
        request_id = uuid4()
        knowledge_data = RetrieveTrainingKnowledgeOutput(
            query_status="SUCCEEDED" if state.knowledge_results else "EMPTY",
            index_id="weekly-review-request",
            corpus_root_hash="0" * 64,
            results=state.knowledge_results,
            limitations=[],
        )
        context = AgentContext(
            request_id=request_id,
            user_id=state.user_id,
            intent=AgentIntent.WEEKLY_REVIEW,
            current_time=datetime.now(ZoneInfo(state.request.timezone)),
            timezone=state.request.timezone,
            recent_training=state.weekly_facts.model_dump(mode="json"),
            applicable_rules=[{"code": item} for item in state.rule_results],
            data_quality=state.weekly_facts.data_quality.model_dump(mode="json"),
            tool_results=(
                [
                    AgentToolResult(
                        tool_call_id=uuid4(),
                        tool_name="retrieve_training_knowledge",
                        status=AgentToolStatus.SUCCEEDED,
                        data=knowledge_data.model_dump(mode="json"),
                    )
                ]
                if state.knowledge_results
                else []
            ),
        )
        output = self.gateway.generate(
            system_instructions=(
                "Generate a concise weekly running review. Only explain the canonical weekly facts "
                "and rules in context. Never claim to modify a plan. Return the existing strict "
                "AgentModelOutput JSON contract and select only request-local knowledge IDs."
            ),
            user_message="Explain this week's canonical training facts and next-week review focus.",
            context=context,
            tools=[],
            trace=AgentTrace(request_id=request_id),
        )
        if output.intent != AgentIntent.WEEKLY_REVIEW or not output.answer:
            raise ValueError("Provider weekly review output is invalid")
        facts = state.weekly_facts
        return WeeklyReviewDraft(
            overview=output.answer,
            completion_summary=(
                f"计划 {facts.planned.planned_running_session_count} 次，"
                f"完成 {facts.completed.completed_running_session_count} 次，"
                f"部分完成 {facts.completed.partial_session_count} 次。"
            ),
            key_session_summary=(
                f"关键课计划 {facts.planned.planned_key_session_count} 次，"
                f"完成 {facts.completed.completed_key_session_count} 次。"
            ),
            deviation_summary=f"确定性偏差 {len(facts.deviations)} 项。",
            fatigue_and_risk=(
                f"疲劳状态 {facts.runner_state_trend.fatigue_level}；"
                "风险结论只保留服务端已有警告。"
            ),
            next_week_focus=[output.summary] if output.summary else [],
            knowledge_reference_ids=output.knowledge_reference_ids,
        )


class KnowledgeToolWeeklyRetriever:
    def __init__(self, tool: RetrieveTrainingKnowledgeTool, *, timezone: str = "Asia/Shanghai") -> None:
        self.tool = tool
        self.timezone = timezone

    def __call__(self, *, query: str, user_id: int) -> RetrieveTrainingKnowledgeOutput:
        request_id = uuid4()
        context = AgentContext(
            request_id=request_id,
            user_id=user_id,
            intent=AgentIntent.WEEKLY_REVIEW,
            current_time=datetime.now(ZoneInfo(self.timezone)),
            timezone=self.timezone,
        )
        return self.tool.execute(
            RetrieveTrainingKnowledgeInput(query=query, top_k=min(4, self.tool.maximum_top_k)),
            context,
        )


class StructuredWeeklyReviewGenerator:
    def __init__(
        self,
        provider: StructuredTaskProvider,
        settings: Settings,
        *,
        db: Session | None = None,
    ) -> None:
        self.provider = provider
        self.profile = task_model_profile(settings, ModelTaskType.WEEKLY_REVIEW_ANALYSIS)
        self.db = db

    def __call__(self, state: WeeklyReviewState) -> WeeklyReviewAnalysis:
        if state.weekly_facts is None:
            raise ValueError("Weekly facts are required")
        references = [
            {
                "id": item.knowledge_reference_id,
                "title": item.title,
                "section": item.section,
                "excerpt": item.excerpt,
                "limitations": item.limitations,
            }
            for item in state.knowledge_results
        ]
        result = self.provider.generate(
            profile=self.profile,
            schema=WeeklyReviewAnalysis,
            system_prompt=(
                "Analyze canonical running facts without changing any plan. Treat deterministic rules, "
                "decision readiness, warnings and limitations as authoritative. Return only the requested "
                "JSON schema. Do not diagnose injury or invent missing recovery facts."
            ),
            input_payload={
                "weekly_facts": state.weekly_facts.model_dump(mode="json"),
                "deterministic_rules": state.rule_results,
                "warnings": state.warnings,
                "limitations": state.limitations,
                "knowledge_references": references,
            },
        )
        if self.db is not None:
            persist_reasoning(
                self.db,
                user_id=state.user_id,
                provider="openai-compatible",
                profile=self.profile,
                result=result,
                related_record_type="weekly_facts",
            )
        return cast(WeeklyReviewAnalysis, result.value)


class StructuredPlanDesigner:
    def __init__(
        self,
        provider: StructuredTaskProvider,
        settings: Settings,
        *,
        db: Session | None = None,
    ) -> None:
        self.provider = provider
        self.profile = task_model_profile(settings, ModelTaskType.PLAN_DESIGN)
        self.db = db

    def __call__(self, state: WeeklyReviewState) -> PlanDesignAnalysis:
        if state.weekly_facts is None or state.weekly_analysis is None:
            raise ValueError("Validated weekly analysis is required")
        result = self.provider.generate(
            profile=self.profile,
            schema=PlanDesignAnalysis,
            system_prompt=(
                "Design conservative candidate changes for the supplied existing plan. Use only supplied "
                "plan IDs and rule codes. Do not mutate data. Partial readiness never authorizes an increase. "
                "Return only the requested JSON schema for deterministic server materialization."
            ),
            input_payload={
                "weekly_review_analysis": state.weekly_analysis.model_dump(mode="json"),
                "weekly_classification": state.weekly_facts.classification.model_dump(mode="json"),
                "runner_state": state.weekly_facts.runner_state_trend.model_dump(mode="json"),
                "target_plans": [item.model_dump(mode="json") for item in state.target_plans],
                "deterministic_rules": state.rule_results,
                "knowledge_reference_ids": state.weekly_analysis.knowledge_reference_ids,
            },
        )
        if self.db is not None:
            persist_reasoning(
                self.db,
                user_id=state.user_id,
                provider="openai-compatible",
                profile=self.profile,
                result=result,
                related_record_type="weekly_facts",
            )
        return cast(PlanDesignAnalysis, result.value)


class DeterministicProposalMaterializer:
    def __init__(self, service: AdaptivePlanProposalService | None = None) -> None:
        self.service = service or AdaptivePlanProposalService()

    def __call__(self, state: WeeklyReviewState):
        if state.weekly_facts is None or state.plan_design is None:
            raise ValueError("Weekly facts and plan design are required")
        return self.service.create_proposal(
            user_id=state.user_id,
            weekly_facts=state.weekly_facts,
            target_plans=state.target_plans,
            candidates=state.plan_design.candidate_adjustments,
        )
