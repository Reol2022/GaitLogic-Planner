from __future__ import annotations

from dataclasses import dataclass

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentTraceEventType, AgentTraceStatus
from server.agent.schemas import AgentContext, AgentNotice, AgentTodayRecommendation
from server.agent.today_recommendation import canonical_today_decision, contextual_evidence
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
        risk = AgentRiskLevel.UNKNOWN

        if intent == AgentIntent.TODAY_RECOMMENDATION:
            evaluation = context.today_evaluation or {}
            decision = canonical_today_decision(evaluation)
            planned_status = str((context.today_workout or {}).get("workout_status") or "UNKNOWN")
            risk_value = str(evaluation.get("risk_level") or "UNKNOWN")
            risk = AgentRiskLevel(risk_value) if risk_value in AgentRiskLevel._value2member_map_ else AgentRiskLevel.UNKNOWN
            headline_map = {
                "PROCEED": "可以按原计划执行。" if chinese else "Proceed with the existing plan.",
                "PROCEED_WITH_CAUTION": "建议谨慎执行原计划。" if chinese else "Proceed cautiously with the existing plan.",
                "CONSIDER_ADJUSTMENT": "建议考虑调整，但系统没有修改计划。" if chinese else "Consider an adjustment; no plan was changed.",
                "REST_OR_RECOVERY": "规则建议休息或恢复。" if chinese else "The rules recommend rest or recovery.",
                "UNKNOWN": "数据不足，无法给出确定的今日建议。" if chinese else "Available data is insufficient for a definite recommendation.",
            }
            evidence = contextual_evidence(context)[:5]
            quality = str((context.data_quality or {}).get("data_status") or "UNKNOWN")
            recommendation = AgentTodayRecommendation(
                decision=decision,
                planned_workout_status=planned_status,
                headline=headline_map[decision],
                key_evidence=evidence,
                data_quality=quality,
            )
            if risk == AgentRiskLevel.HIGH:
                warnings.append(
                    AgentNotice(
                        code="HIGH_RISK_REVIEW_REQUIRED",
                        message=(
                            "现有规则包含高关注提示，请先人工复核。"
                            if chinese
                            else "Existing rules contain a high-attention warning; review it manually first."
                        ),
                    )
                )
            answer = (
                f"今日建议：{recommendation.headline} 依据：当前确定性规则结果为 {decision}。"
                if chinese
                else f"Today's recommendation: {recommendation.headline} Deterministic rule result: {decision}."
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
        return DeterministicFallbackResult(
            answer=answer,
            summary=summary,
            risk_level=risk,
            today_recommendation=recommendation,
            warnings=warnings,
            limitations=[limitation],
        )
