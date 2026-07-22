from server.agent.enums import AgentIntent
from server.agent.fallback import DeterministicCoachFallback
from server.agent.schemas import AgentContext, AgentRequest
from tests.agent_tool_fakes import NOW


def context(*, planned="PLANNED", decision="passed_with_notice", data_status="AVAILABLE", risk="MODERATE"):
    request = AgentRequest(user_id=121, message="fictional", intent=AgentIntent.TODAY_RECOMMENDATION)
    return AgentContext(
        request_id=request.request_id,
        user_id=121,
        intent=request.intent,
        current_time=NOW,
        timezone="Asia/Shanghai",
        today_workout={"workout_status": planned},
        today_evaluation={
            "data_status": data_status,
            "decision": decision,
            "risk_level": risk,
            "rule_hits": [{"rule_code": "FICTIONAL_RULE", "explanation": "Existing evidence."}],
            "evidence": ["existing_metric"],
        },
        data_quality={"data_status": data_status},
    )


def test_fallback_restates_caution_without_modifying_plan() -> None:
    result = DeterministicCoachFallback().build(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        message="今天跑什么？",
        context=context(),
    )
    assert result.today_recommendation.decision == "PROCEED_WITH_CAUTION"
    assert "没有修改" not in result.answer
    assert result.limitations[0].code == "MODEL_EXPLANATION_UNAVAILABLE"


def test_fallback_handles_no_plan_rest_and_unknown_without_inventing_workout() -> None:
    cases = [
        context(planned="NO_PLAN", decision="passed", data_status="UNKNOWN", risk="UNKNOWN"),
        context(planned="REST_DAY", decision="needs_review"),
        context(planned="CYCLE_NOT_ACTIVE", decision="passed", data_status="UNKNOWN", risk="UNKNOWN"),
    ]
    for item in cases:
        result = DeterministicCoachFallback().build(
            intent=AgentIntent.TODAY_RECOMMENDATION,
            message="今天怎么办？",
            context=item,
        )
        assert result.today_recommendation.planned_workout_status == item.today_workout["workout_status"]
        assert " km" not in result.answer
        assert "配速" not in result.answer


def test_fallback_preserves_high_risk_warning() -> None:
    result = DeterministicCoachFallback().build(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        message="today?",
        context=context(risk="HIGH"),
    )
    assert result.warnings


def test_explain_and_general_fallbacks_are_finite() -> None:
    base = context()
    explain = base.model_copy(update={"intent": AgentIntent.EXPLAIN_RUNNER_STATE, "runner_state": {"overall_state": "UNKNOWN"}})
    general = base.model_copy(update={"intent": AgentIntent.GENERAL_TRAINING_QUESTION})
    assert "UNKNOWN" in DeterministicCoachFallback().build(intent=explain.intent, message="explain", context=explain).answer
    assert "unavailable" in DeterministicCoachFallback().build(intent=general.intent, message="question", context=general).answer.lower()
