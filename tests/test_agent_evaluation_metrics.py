from server.agent.evaluation.metrics import calculate_summary
from server.agent.evaluation.schemas import (
    EvaluationAssertion,
    EvaluationCaseResult,
)


def result(*, passed: bool, fallback: bool = False) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id="metric_case",
        category="general_training_question",
        passed=passed,
        intent="GENERAL_TRAINING_QUESTION",
        actual_intent="GENERAL_TRAINING_QUESTION",
        status="DEGRADED" if fallback else "SUCCEEDED",
        expected_tools=["get_training_rules"],
        actual_context_tools=["get_training_rules"],
        actual_model_tools=[],
        assertions=[EvaluationAssertion(code="TEST", passed=passed, detail="fixture")],
        safe_error_codes=[],
        duration_ms=1,
        used_fallback=fallback,
        required_tool_hits=1,
        required_tool_total=1,
        forbidden_tool_called=False,
        tool_arguments_valid=True,
        unsupported_claim_found=False,
        rule_violation_found=False,
    )


def test_metrics_calculate_real_denominators() -> None:
    summary = calculate_summary([result(passed=True), result(passed=False, fallback=True)])
    assert summary.case_pass_rate == 0.5
    assert summary.required_tool_recall == 1
    assert summary.fallback_success_rate == 0
    assert summary.forbidden_tool_call_rate == 0


def test_metrics_handle_empty_input_without_division_error() -> None:
    summary = calculate_summary([])
    assert summary.total_cases == 0
    assert summary.case_pass_rate == 0
    assert summary.intent_accuracy == 0
    assert summary.required_tool_recall == 1
