import pytest
from pydantic import ValidationError

from server.agent.evaluation.schemas import CoachEvaluationCase


def valid_case() -> dict:
    return {
        "case_id": "today_test_001",
        "category": "today_recommendation",
        "title": "Fictional test",
        "question": "What should I do today?",
        "intent": "TODAY_RECOMMENDATION",
        "fixture": "normal_training",
        "expected_status": ["SUCCEEDED"],
        "expected_context_tools": ["get_runner_state"],
        "expected_model_tools": [],
        "allowed_extra_tools": [],
        "forbidden_tools": [],
        "expected_decision": "PROCEED",
        "expected_planned_status": "PLANNED",
        "required_warning_codes": [],
        "requires_limitation": False,
        "forbidden_claims": [],
    }


def test_valid_case_uses_strict_public_contract() -> None:
    case = CoachEvaluationCase.model_validate(valid_case())
    assert case.case_id == "today_test_001"

    with pytest.raises(ValidationError):
        CoachEvaluationCase.model_validate({**valid_case(), "unknown": True})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("intent", "WEEKLY_REVIEW"),
        ("expected_decision", "MADE_UP"),
        ("expected_context_tools", ["write_training_plan"]),
    ],
)
def test_case_rejects_non_public_contract_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CoachEvaluationCase.model_validate({**valid_case(), field: value})


def test_non_today_case_cannot_claim_today_decision() -> None:
    payload = {
        **valid_case(),
        "category": "explain_runner_state",
        "intent": "EXPLAIN_RUNNER_STATE",
    }
    with pytest.raises(ValidationError):
        CoachEvaluationCase.model_validate(payload)
