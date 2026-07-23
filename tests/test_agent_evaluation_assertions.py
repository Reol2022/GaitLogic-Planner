from uuid import uuid4

from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus, AgentToolStatus
from server.agent.evaluation.assertions import (
    evaluate_assertions,
    find_rule_violations,
    find_unsupported_claims,
)
from server.agent.evaluation.fixtures import (
    EVALUATION_FIXTURES,
    EVALUATION_NOW,
    build_evaluation_registry,
)
from server.agent.evaluation.schemas import CoachEvaluationCase
from server.agent.schemas import (
    AgentContext,
    AgentResponse,
    AgentTodayRecommendation,
)
from tests.test_agent_evaluation_schemas import valid_case


def response(*, answer: str = "Safe fictional explanation.") -> AgentResponse:
    return AgentResponse(
        request_id=uuid4(),
        trace_id=uuid4(),
        status=AgentRunStatus.SUCCEEDED,
        intent=AgentIntent.TODAY_RECOMMENDATION,
        answer=answer,
        risk_level=AgentRiskLevel.LOW,
        today_recommendation=AgentTodayRecommendation(
            decision="PROCEED",
            planned_workout_status="PLANNED",
            headline="Proceed using fictional deterministic rules.",
            data_quality="AVAILABLE",
        ),
    )


def test_assertions_detect_forbidden_tool_and_unsupported_claim() -> None:
    case = CoachEvaluationCase.model_validate(
        {
            **valid_case(),
            "expected_context_tools": [],
            "forbidden_tools": ["get_recent_training"],
            "forbidden_claims": ["secret fictional claim"],
        }
    )
    actual = response(answer="secret fictional claim")
    assertions, unsupported, _violations = evaluate_assertions(
        case=case,
        response=actual,
        public_status="SUCCEEDED",
        context_tools=[],
        model_tools=["get_recent_training"],
    )
    failed = {item.code for item in assertions if not item.passed}
    assert "NO_FORBIDDEN_TOOLS" in failed
    assert "UNSUPPORTED_CLAIMS" in failed
    assert unsupported


def test_rule_assertion_detects_decision_override_and_missing_high_warning() -> None:
    case = CoachEvaluationCase.model_validate(
        {
            **valid_case(),
            "expected_decision": "REST_OR_RECOVERY",
            "required_warning_codes": ["HIGH_RISK_REVIEW_REQUIRED"],
        }
    )
    actual = response()
    actual.risk_level = AgentRiskLevel.HIGH
    violations = find_rule_violations(case, actual)
    assert "DETERMINISTIC_DECISION_OVERRIDDEN" in violations
    assert "HIGH_RISK_WARNING_MISSING" in violations
    assert not find_unsupported_claims(case, response())


def test_production_shaped_registry_rejects_invalid_tool_arguments() -> None:
    registry = build_evaluation_registry(EVALUATION_FIXTURES["normal_training"])
    context = AgentContext(
        request_id=uuid4(),
        user_id=70001,
        intent=AgentIntent.TODAY_RECOMMENDATION,
        current_time=EVALUATION_NOW,
        timezone="Asia/Shanghai",
    )
    result = registry.invoke("get_recent_training", {"days": 999, "limit": 20}, context)
    assert result.status == AgentToolStatus.INVALID_ARGUMENTS
