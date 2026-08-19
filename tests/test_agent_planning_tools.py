from types import SimpleNamespace

from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.tools.planning_tools import GetCurrentTrainingCycleTool, GetTodayWorkoutTool
from server.agent.tools.schemas import EmptyToolInput, TrainingDataStatus
from tests.agent_tool_fakes import FakeDependencies, NOW


def context(user_id: int = 61) -> AgentContext:
    request = AgentRequest(user_id=user_id, message="fictional", intent=AgentIntent.TODAY_RECOMMENDATION)
    return AgentContext(request_id=request.request_id, user_id=user_id, intent=request.intent, current_time=NOW, timezone="Asia/Shanghai")


def test_today_distinguishes_inactive_cycle_from_no_plan() -> None:
    deps = FakeDependencies()
    inactive = GetTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert inactive.workout_status == "CYCLE_NOT_ACTIVE"
    deps.today = (NOW.date(), SimpleNamespace(id=1), [])
    no_plan = GetTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert no_plan.workout_status == "NO_PLAN"


def test_today_rest_and_plan_are_read_without_inventing_segments() -> None:
    deps = FakeDependencies()
    rest = SimpleNamespace(
        main_type_normalized=WorkoutMainTypeNormalized.rest,
        planned_content="Rest",
        planned_distance_km=None,
        target_pace_text=None,
        focus_note="Recover",
        workout_log=None,
    )
    deps.today = (NOW.date(), SimpleNamespace(id=1), [rest])
    output = GetTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert output.workout_status == "REST_DAY"
    assert output.segments == []
    assert output.limitations[0].message == "当前训练计划以文本保存训练内容，系统不会推测或虚构结构化训练分段。"

    rest.main_type_normalized = WorkoutMainTypeNormalized.easy
    rest.workout_log = SimpleNamespace(status_normalized=WorkoutStatusNormalized.completed_normal)
    output = GetTodayWorkoutTool(deps).execute(EmptyToolInput(), context())
    assert output.workout_status == "PLANNED"
    assert output.completion_status == "completed_normal"


def test_current_cycle_is_bounded_and_progress_is_not_invented() -> None:
    deps = FakeDependencies()
    blocks = [
        SimpleNamespace(
            id=index, sort_order=index, block_name=f"Week {index}", start_date=NOW.date(),
            end_date=NOW.date(), phase_name="BASE", focus="fictional focus " * 40,
        )
        for index in range(1, 5)
    ]
    deps.cycle = SimpleNamespace(
        id=8, name="Fictional cycle", actual_start_date=NOW.date(), start_date=NOW.date(),
        actual_end_date=None, end_date=None, goal="Fictional race", blocks=blocks,
    )
    output = GetCurrentTrainingCycleTool(deps, block_limit=2).execute(EmptyToolInput(), context())
    assert output.data_status == TrainingDataStatus.AVAILABLE
    assert output.progress is None
    assert len(output.weekly_structure) == 2
    assert all(len(item.focus or "") <= 240 for item in output.weekly_structure)


def test_no_current_cycle_is_not_found() -> None:
    output = GetCurrentTrainingCycleTool(FakeDependencies()).execute(EmptyToolInput(), context())
    assert output.data_status == TrainingDataStatus.NOT_FOUND
