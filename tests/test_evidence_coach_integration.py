from __future__ import annotations

from datetime import date

from server.agent.context import AgentContextBuilder
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus, AgentToolStatus
from server.agent.gateway import MockAgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentLimits, AgentModelOutput, AgentRequest, AgentToolResult
from server.domain.decision_readiness import DecisionReadiness
from tests.test_evidence_reflect import RecentTool, registry


class PreloadedContextBuilder(AgentContextBuilder):
    def __init__(self, result: AgentToolResult | None = None) -> None:
        super().__init__()
        self.result = result

    def build(self, request, seed=None, *, trace=None):
        del trace
        context = super().build(request, seed)
        if self.result is None:
            return context
        return context.model_copy(update={"tool_results": [self.result]})


def request(message: str) -> AgentRequest:
    return AgentRequest(
        user_id=7001,
        message=message,
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
    )


def output(answer: str) -> AgentModelOutput:
    return AgentModelOutput(
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        answer=answer,
        risk_level=AgentRiskLevel.UNKNOWN,
    )


def test_coach_runs_judge_reflect_targeted_tool_rejudge_then_analysis() -> None:
    tool = RecentTool()
    agent = GaitLogicCoachAgent(
        gateway=MockAgentLLMGateway(output("最近训练事实可用于回答跑量问题。")),
        registry=registry(tool),
        context_builder=PreloadedContextBuilder(),
        limits=AgentLimits(max_reflect_rounds=1, max_tool_calls=6),
    )
    response = agent.run(request("我最近一周跑了多少？"))
    assert response.status == AgentRunStatus.SUCCEEDED
    assert tool.calls == 1
    assert agent.last_context.reflect_summary.triggered is True
    assert agent.last_context.reflect_summary.rounds == 1
    assert agent.last_context.decision_readiness[0].readiness == DecisionReadiness.READY


def test_coach_does_not_reflect_when_required_evidence_is_already_present() -> None:
    result = AgentToolResult(
        tool_call_id="5ef6ac0d-b831-455c-bdf5-664af0f59a50",
        tool_name="get_recent_training",
        status=AgentToolStatus.SUCCEEDED,
        data={
            "data_status": "AVAILABLE",
            "as_of": date(2026, 8, 20).isoformat(),
            "items": [],
            "summary": {
                "total_sessions": 0,
                "total_distance_km": 0,
                "completed_key_sessions": 0,
                "rest_days": 7,
            },
            "data_quality": {"level": "HIGH", "completeness": 1, "missing_fields": []},
            "missing_reasons": [],
        },
    )
    tool = RecentTool()
    agent = GaitLogicCoachAgent(
        gateway=MockAgentLLMGateway(output("已有跑量事实，可以回答。")),
        registry=registry(tool),
        context_builder=PreloadedContextBuilder(result),
        limits=AgentLimits(max_reflect_rounds=1),
    )
    response = agent.run(request("我最近一周跑了多少？"))
    assert response.status == AgentRunStatus.SUCCEEDED
    assert tool.calls == 0
    assert agent.last_context.reflect_summary.triggered is False


def test_coach_keeps_partial_answer_when_missing_fact_cannot_be_filled() -> None:
    agent = GaitLogicCoachAgent(
        gateway=MockAgentLLMGateway(output("恢复数据不足，当前暂不判断恢复状态。")),
        registry=AgentToolRegistry(),
        context_builder=PreloadedContextBuilder(),
        limits=AgentLimits(max_reflect_rounds=1),
    )
    response = agent.run(request("最近恢复怎么样？"))
    assert response.status == AgentRunStatus.SUCCEEDED
    assert all(
        item.readiness == DecisionReadiness.BLOCKED
        for item in agent.last_context.decision_readiness
    )
    assert agent.last_context.reflect_summary.triggered is False
    assert "reasoning_content" not in agent.last_context.model_dump(mode="json")
