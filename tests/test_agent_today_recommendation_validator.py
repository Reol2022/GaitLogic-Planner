from __future__ import annotations

import pytest

from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.errors import AgentErrorCode
from server.agent.schemas import (
    AgentContext,
    AgentModelOutput,
    AgentNotice,
    AgentRequest,
    AgentTodayRecommendation,
)
from server.agent.today_recommendation import TodayRecommendationValidator, canonical_today_decision
from tests.agent_tool_fakes import NOW


def context(*, source_decision="passed", planned="PLANNED", risk="LOW", data_status="AVAILABLE"):
    request = AgentRequest(user_id=111, message="fictional", intent=AgentIntent.TODAY_RECOMMENDATION)
    return AgentContext(
        request_id=request.request_id,
        user_id=111,
        intent=request.intent,
        current_time=NOW,
        timezone="Asia/Shanghai",
        today_workout={"workout_status": planned, "distance_or_duration_target": "8.00 km"},
        today_evaluation={
            "data_status": data_status,
            "decision": source_decision,
            "risk_level": risk,
            "rule_hits": [
                {
                    "rule_code": "TODAY_PUBLIC_RULE",
                    "severity": "notice",
                    "action": "monitor",
                    "explanation": "Existing rule evidence.",
                }
            ],
            "evidence": ["distance_7d_km"],
        },
        data_quality={"data_status": "AVAILABLE"},
    )


def output(decision: str, *, planned="PLANNED", answer="Use the existing plan.", evidence=None, warnings=None, limitations=None):
    return AgentModelOutput(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        answer=answer,
        risk_level=AgentRiskLevel.UNKNOWN,
        warnings=warnings or [],
        limitations=limitations or [],
        today_recommendation=AgentTodayRecommendation(
            decision=decision,
            planned_workout_status=planned,
            headline=answer,
            key_evidence=evidence or ["TODAY_PUBLIC_RULE"],
            data_quality="AVAILABLE",
        ),
    )


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("passed", "PROCEED"),
        ("passed_with_notice", "PROCEED_WITH_CAUTION"),
        ("adjustment_recommended", "CONSIDER_ADJUSTMENT"),
        ("auto_apply_blocked", "CONSIDER_ADJUSTMENT"),
    ],
)
def test_decision_mapping_and_alignment(source: str, canonical: str) -> None:
    ctx = context(source_decision=source)
    assert canonical_today_decision(ctx.today_evaluation) == canonical
    assert TodayRecommendationValidator().validate(output(canonical), ctx) == []


def test_unknown_requires_limitation() -> None:
    ctx = context(source_decision="passed", data_status="UNKNOWN")
    errors = TodayRecommendationValidator().validate(output("UNKNOWN"), ctx)
    assert AgentErrorCode.AGENT_VALIDATION_FAILED in errors
    safe = output(
        "UNKNOWN",
        limitations=[AgentNotice(code="DATA_LIMITED", message="Available data is limited.")],
    )
    assert TodayRecommendationValidator().validate(safe, ctx) == []


def test_high_risk_requires_warning() -> None:
    ctx = context(risk="HIGH")
    assert AgentErrorCode.AGENT_VALIDATION_FAILED in TodayRecommendationValidator().validate(output("PROCEED"), ctx)
    safe = output(
        "PROCEED",
        warnings=[AgentNotice(code="HIGH_RISK", message="Review the existing warning.")],
    )
    assert TodayRecommendationValidator().validate(safe, ctx) == []


@pytest.mark.parametrize(
    ("ctx", "candidate"),
    [
        (context(planned="NO_PLAN"), output("PROCEED", planned="NO_PLAN", answer="Run 5 km.")),
        (context(planned="REST_DAY"), output("REST_OR_RECOVERY", planned="REST_DAY", answer="Do high-intensity intervals.")),
        (context(), output("PROCEED", evidence=["NONEXISTENT_EVIDENCE"])),
        (context(), output("PROCEED", answer="Run 99 km.")),
        (context(), output("PROCEED", answer="I changed your training plan.")),
        (context(), output("PROCEED", answer="You have an injury.")),
        (context(), output("PROCEED", answer="This is absolutely safe.")),
    ],
)
def test_unsafe_or_invented_recommendations_are_rejected(ctx, candidate) -> None:
    assert TodayRecommendationValidator().validate(candidate, ctx)


def test_planned_status_must_match_context() -> None:
    errors = TodayRecommendationValidator().validate(output("PROCEED", planned="REST_DAY"), context())
    assert AgentErrorCode.AGENT_VALIDATION_FAILED in errors
