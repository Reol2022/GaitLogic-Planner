from __future__ import annotations

from dataclasses import dataclass

from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentToolStatus,
    AgentTraceEventType,
    AgentTraceStatus,
)
from server.agent.knowledge_references import KNOWLEDGE_TOOL_NAME
from server.agent.schemas import AgentContext, AgentNotice, AgentTodayRecommendation
from server.agent.today_recommendation import build_authoritative_today_facts
from server.agent.trace import AgentTrace


@dataclass(frozen=True)
class DeterministicFallbackResult:
    answer: str
    summary: str
    risk_level: AgentRiskLevel
    today_recommendation: AgentTodayRecommendation | None
    warnings: list[AgentNotice]
    limitations: list[AgentNotice]


class DeterministicCoachFallback:
    """Finite templates that only restate already-computed product facts."""

    @staticmethod
    def _is_chinese(message: str) -> bool:
        return any("\u4e00" <= character <= "\u9fff" for character in message)

    def build(
        self,
        *,
        intent: AgentIntent,
        message: str,
        context: AgentContext,
        trace: AgentTrace | None = None,
    ) -> DeterministicFallbackResult:
        if trace is not None:
            trace.add_event(AgentTraceEventType.FALLBACK_STARTED, AgentTraceStatus.STARTED)
        chinese = self._is_chinese(message)
        limitation = AgentNotice(
            code="MODEL_EXPLANATION_UNAVAILABLE",
            message=(
                "模型解释服务暂不可用；以下内容只复述系统规则和已有数据。"
                if chinese
                else "Model explanation is unavailable; this response only restates system rules and available data."
            ),
        )
        recommendation = None
        warnings: list[AgentNotice] = []
        authoritative_limitations: list[AgentNotice] = []
        risk = AgentRiskLevel.UNKNOWN

        if intent == AgentIntent.TODAY_RECOMMENDATION:
            facts = build_authoritative_today_facts(
                context,
                user_message=message,
            )
            recommendation = facts.recommendation
            risk = facts.risk_level
            warnings = facts.warnings
            authoritative_limitations = facts.limitations
            answer = (
                f"今日建议：{recommendation.headline} 依据：当前确定性规则结果为 {recommendation.decision}。"
                if chinese
                else f"Today's recommendation: {recommendation.headline} Deterministic rule result: {recommendation.decision}."
            )
            summary = recommendation.headline
        elif intent == AgentIntent.EXPLAIN_RUNNER_STATE:
            state = context.runner_state or {}
            overall = str(state.get("overall_state") or "UNKNOWN")
            answer = (
                f"当前系统状态为 {overall}。模型解释暂不可用，请以状态 Evidence 和数据质量为准。"
                if chinese
                else f"The current system state is {overall}. Model explanation is unavailable; rely on the recorded evidence and data quality."
            )
            summary = f"Runner State: {overall}"
        else:
            answer = (
                "模型解释暂不可用。当前只能提供已注册的公开训练规则摘要，不能生成新的训练结论。"
                if chinese
                else "Model explanation is unavailable. Only registered public rule summaries are available; no new training conclusion was generated."
            )
            summary = "Model explanation unavailable"

        if trace is not None:
            trace.add_event(AgentTraceEventType.FALLBACK_COMPLETED, AgentTraceStatus.SUCCEEDED)
        knowledge_failed = any(
            result.tool_name == KNOWLEDGE_TOOL_NAME
            and result.status != AgentToolStatus.SUCCEEDED
            for result in context.tool_results
        )
        fallback_limitations = [*authoritative_limitations[:19], limitation]
        if knowledge_failed:
            fallback_limitations = [
                *fallback_limitations[:19],
                AgentNotice(
                    code="KNOWLEDGE_RETRIEVAL_UNAVAILABLE",
                    message=(
                        "训练知识检索暂不可用；当前回答未使用知识库引用。"
                        if chinese
                        else "Training knowledge retrieval is unavailable; no knowledge reference was used."
                    ),
                ),
            ]
        return DeterministicFallbackResult(
            answer=answer,
            summary=summary,
            risk_level=risk,
            today_recommendation=recommendation,
            warnings=warnings,
            limitations=fallback_limitations,
        )
