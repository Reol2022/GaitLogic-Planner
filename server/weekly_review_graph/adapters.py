from __future__ import annotations

from datetime import datetime
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
