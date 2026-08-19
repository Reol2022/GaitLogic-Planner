from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.tools.runner_state_tools import GetRunnerStateHistoryTool, GetRunnerStateTool
from server.agent.tools.schemas import EmptyToolInput, RunnerStateHistoryInput, TrainingDataStatus
from tests.agent_tool_fakes import FakeDependencies, NOW


def context(user_id: int = 41) -> AgentContext:
    return AgentContext(
        request_id=AgentRequest(user_id=user_id, message="fictional", intent=AgentIntent.EXPLAIN_RUNNER_STATE).request_id,
        user_id=user_id,
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        current_time=NOW,
        timezone="Asia/Shanghai",
    )


def test_current_state_preserves_unknown_and_never_exposes_runner_id() -> None:
    deps = FakeDependencies()
    output = GetRunnerStateTool(deps).execute(EmptyToolInput(), context(771))
    assert output.overall_state == "UNKNOWN"
    assert output.data_status == TrainingDataStatus.UNKNOWN
    assert deps.seen_user_ids == [771]
    assert "runner_id" not in output.model_dump_json()


def test_evidence_is_bounded() -> None:
    deps = FakeDependencies()
    output = GetRunnerStateTool(deps, evidence_limit=1).execute(EmptyToolInput(), context())
    assert len(output.evidence) <= 3
    assert all("_" not in item.message for item in output.limitations)


def test_history_is_summary_only_and_bounded() -> None:
    deps = FakeDependencies()
    deps.history_items = [
        SimpleNamespace(
            id=index,
            created_at=datetime(2026, 7, index, tzinfo=ZoneInfo("Asia/Shanghai")),
            trigger_type=SimpleNamespace(value="MANUAL"),
            fatigue_state="NORMAL",
            risk_flag_count=0,
            distance_7d_km=10.0,
            distance_28d_km=40.0,
            volume_trend="STABLE",
            training_consistency="HIGH",
            training_phase="BASE",
            data_completeness=0.9,
        )
        for index in range(1, 10)
    ]
    output = GetRunnerStateHistoryTool(deps, history_limit=3).execute(
        RunnerStateHistoryInput(limit=7), context()
    )
    assert len(output.items) == 3
    serialized = output.model_dump_json()
    assert "snapshot_payload" not in serialized
    assert "trigger_reference" not in serialized
