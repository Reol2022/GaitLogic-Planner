from datetime import date

import pytest
from pydantic import ValidationError

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.tools.schemas import RecentTrainingInput, TrainingDataQualityInput, TrainingDataStatus
from server.agent.tools.training_tools import GetRecentTrainingTool, GetTrainingDataQualityTool
from server.schemas.training_read import RecentTrainingSessionRead
from tests.agent_tool_fakes import FakeDependencies, NOW


def context(user_id: int = 51) -> AgentContext:
    request = AgentRequest(user_id=user_id, message="fictional", intent=AgentIntent.WEEKLY_REVIEW)
    return AgentContext(request_id=request.request_id, user_id=user_id, intent=request.intent, current_time=NOW, timezone="Asia/Shanghai")


def test_recent_training_empty_is_not_found_not_failure() -> None:
    output = GetRecentTrainingTool(FakeDependencies()).execute(RecentTrainingInput(), context())
    assert output.data_status == TrainingDataStatus.NOT_FOUND
    assert output.summary.total_sessions == 0


def test_recent_training_normalizes_sources_and_truncates_items() -> None:
    deps = FakeDependencies()
    deps.recent = deps.recent.model_copy(
        update={
            "items": [
                RecentTrainingSessionRead(
                    date=date(2026, 7, 21), training_type="easy", planned_or_unplanned="PLANNED",
                    completion_status="completed_normal", distance_km=8, duration_seconds=3000,
                    average_pace_seconds_per_km=375, average_heart_rate=141, rpe=4,
                    source="GARMIN", brief_review="fictional review", is_key_session=False,
                ),
                RecentTrainingSessionRead(
                    date=date(2026, 7, 20), training_type="tempo", planned_or_unplanned="UNPLANNED",
                    completion_status="completed_normal", source="MANUAL", is_key_session=True,
                ),
            ],
            "total_sessions": 2,
        }
    )
    deps.quality = deps.quality.model_copy(update={"valid_workout_count": 2, "missing_fields": ["heart_rate"]})
    output = GetRecentTrainingTool(deps, item_limit=1).execute(RecentTrainingInput(limit=20), context())
    assert len(output.items) == 1
    assert output.items[0].source == "GARMIN"
    assert output.data_status == TrainingDataStatus.PARTIAL
    assert "external_activity" not in output.model_dump_json().lower()


@pytest.mark.parametrize("payload", [{"days": 0}, {"days": 29}, {"limit": 0}, {"limit": 51}])
def test_recent_training_bounds(payload) -> None:
    with pytest.raises(ValidationError):
        RecentTrainingInput.model_validate(payload)


def test_data_quality_is_completeness_not_risk() -> None:
    output = GetTrainingDataQualityTool(FakeDependencies()).execute(TrainingDataQualityInput(), context())
    assert output.data_status == TrainingDataStatus.UNKNOWN
    assert all("risk" not in item.message.lower() for item in output.limitations)
    assert output.limitations[0].message == "数据完整度只表示当前字段的可用情况，不代表医疗风险或模型置信度。"


@pytest.mark.parametrize("days", [6, 29])
def test_data_quality_window_bounds(days: int) -> None:
    with pytest.raises(ValidationError):
        TrainingDataQualityInput(window_days=days)
