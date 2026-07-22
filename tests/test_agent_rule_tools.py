from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.tools.rule_tools import EvaluateTodayWorkoutTool, GetTrainingRulesTool
from server.agent.tools.schemas import EmptyToolInput, TrainingRulesInput, TrainingDataStatus
from tests.agent_tool_fakes import FakeDependencies, NOW


def context() -> AgentContext:
    request = AgentRequest(user_id=71, message="fictional", intent=AgentIntent.TODAY_RECOMMENDATION)
    return AgentContext(request_id=request.request_id, user_id=71, intent=request.intent, current_time=NOW, timezone="Asia/Shanghai")


def test_rule_scope_is_fixed_and_internal_definition_is_not_returned() -> None:
    deps = FakeDependencies()
    deps.rules = [
        SimpleNamespace(
            code="PUBLIC_RULE", name="Public rule", category="load", description="Safe summary",
            severity="notice", evidence_refs_json=["distance_7d"],
        )
    ]
    output = GetTrainingRulesTool(deps).execute(TrainingRulesInput(scope="TODAY"), context())
    assert output.data_status == TrainingDataStatus.AVAILABLE
    serialized = output.model_dump_json()
    assert "conditions_json" not in serialized
    assert "thresholds_json" not in serialized
    assert "file_path" not in serialized


def test_runner_state_scope_missing_is_explicit() -> None:
    output = GetTrainingRulesTool(FakeDependencies()).execute(
        TrainingRulesInput(scope="RUNNER_STATE"), context()
    )
    assert output.data_status == TrainingDataStatus.NOT_FOUND
    assert output.limitations


def test_illegal_rule_scope_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TrainingRulesInput(scope="PRIVATE")


def evaluation(*, limited: bool, validation_status: str, caution: int = 0):
    hit = SimpleNamespace(
        rule_code="TODAY_PUBLIC_NOTICE", severity="caution", action="monitor",
        explanation="Review the fictional training facts.", output={"evidence": ["fictional metric"]},
    )
    return SimpleNamespace(
        data_limited=limited,
        validation_status=validation_status,
        summary=SimpleNamespace(blocking=0, high=0, caution=caution),
        evaluation=SimpleNamespace(matched_rules=[hit]),
        message="Review the fictional training facts.",
    )


def test_evaluation_reuses_existing_decision_and_is_traceable() -> None:
    deps = FakeDependencies()
    deps.evaluation = evaluation(limited=False, validation_status="passed_with_notice", caution=1)
    output = EvaluateTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert output.decision == "passed_with_notice"
    assert output.risk_level == "MODERATE"
    assert output.rule_hits[0].rule_code == "TODAY_PUBLIC_NOTICE"


def test_data_limited_evaluation_is_unknown_not_technical_failure() -> None:
    deps = FakeDependencies()
    deps.evaluation = evaluation(limited=True, validation_status="passed")
    output = EvaluateTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert output.data_status == TrainingDataStatus.UNKNOWN
    assert output.decision == "UNKNOWN"
    assert output.limitations
