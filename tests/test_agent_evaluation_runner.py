from pathlib import Path

from server.agent.evaluation.loader import load_evaluation_cases
from server.agent.evaluation.runner import CoachAgentEvaluationRunner

CASES = Path("evaluation/coach_agent/cases_v1.jsonl")


def case(case_id: str):
    return next(item for item in load_evaluation_cases(CASES) if item.case_id == case_id)


def test_runner_separates_context_and_model_tools() -> None:
    result = CoachAgentEvaluationRunner().run_case(case("today_001"))
    assert result.passed
    assert set(result.actual_context_tools) == set(result.expected_tools)
    assert result.actual_model_tools == []
    assert result.tool_arguments_valid


def test_runner_preserves_decision_plan_warning_and_limitation() -> None:
    high = CoachAgentEvaluationRunner().run_case(case("today_002"))
    unknown = CoachAgentEvaluationRunner().run_case(case("today_006"))
    assert high.actual_decision == "PROCEED_WITH_CAUTION"
    assert high.warning_retained is True
    assert unknown.actual_planned_status == "NO_PLAN"
    assert unknown.limitation_retained is True


def test_runner_fallback_and_validator_rejection_are_safe() -> None:
    disabled = CoachAgentEvaluationRunner().run_case(case("degraded_001"))
    rejected = CoachAgentEvaluationRunner().run_case(case("degraded_004"))
    assert disabled.status == "DEGRADED"
    assert disabled.used_fallback
    assert rejected.passed
    assert not rejected.unsupported_claim_found


def test_same_case_has_deterministic_semantic_result() -> None:
    runner = CoachAgentEvaluationRunner()
    first = runner.run_case(case("security_004"))
    second = runner.run_case(case("security_004"))
    assert first.model_dump(exclude={"duration_ms"}) == second.model_dump(
        exclude={"duration_ms"}
    )
