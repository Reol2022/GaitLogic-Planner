from __future__ import annotations

from planner_core.enums import WorkoutMainTypeNormalized

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentNotice
from server.agent.tool import AgentTool
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.schemas import (
    CurrentTrainingCycleOutput,
    EmptyToolInput,
    TodayWorkoutOutput,
    TrainingCycleBlockRead,
    TrainingDataStatus,
)


def _clean(value: str | None, limit: int) -> str | None:
    cleaned = " ".join(value.split()) if value else ""
    return cleaned[:limit] or None


def _notice(code: str, message: str) -> AgentNotice:
    return AgentNotice(code=code, message=message)


class GetTodayWorkoutTool(AgentTool):
    name = "get_today_workout"
    description = "Read today's plan without changing or interpreting it as an automatic adjustment."
    input_model = EmptyToolInput
    output_model = TodayWorkoutOutput
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    )

    def __init__(self, dependencies: CoachAgentToolDependencies) -> None:
        self.dependencies = dependencies

    def execute(self, arguments: EmptyToolInput, context: AgentContext) -> TodayWorkoutOutput:
        del arguments
        today, cycle, workouts = self.dependencies.today_workouts(context.user_id)
        if cycle is None:
            return TodayWorkoutOutput(
                data_status=TrainingDataStatus.NOT_FOUND,
                workout_status="CYCLE_NOT_ACTIVE",
                date=today,
            )
        if not workouts:
            return TodayWorkoutOutput(
                data_status=TrainingDataStatus.NOT_FOUND,
                workout_status="NO_PLAN",
                date=today,
            )
        workout = workouts[0]
        training_type = workout.main_type_normalized.value
        is_rest = workout.main_type_normalized == WorkoutMainTypeNormalized.rest
        limitations = []
        if len(workouts) > 1:
            limitations.append(
                _notice(
                    "ADDITIONAL_TODAY_SESSIONS_OMITTED",
                    f"精简结果中省略了另外 {len(workouts) - 1} 项今日计划训练。",
                )
            )
        limitations.append(
            _notice(
                "STRUCTURED_SEGMENTS_UNAVAILABLE",
                "当前训练计划以文本保存训练内容，系统不会推测或虚构结构化训练分段。",
            )
        )
        distance_target = (
            f"{float(workout.planned_distance_km):.2f} km"
            if workout.planned_distance_km is not None
            else None
        )
        log = workout.workout_log
        return TodayWorkoutOutput(
            data_status=TrainingDataStatus.AVAILABLE,
            workout_status="REST_DAY" if is_rest else "PLANNED",
            date=today,
            training_type=training_type,
            title=_clean(workout.planned_content, 160),
            distance_or_duration_target=distance_target,
            pace_target=_clean(workout.target_pace_text, 160),
            heart_rate_target=None,
            segments=[],
            notes=_clean(workout.focus_note, 500),
            completion_status=(log.status_normalized.value if log is not None else "not_started"),
            limitations=limitations,
        )


class GetCurrentTrainingCycleTool(AgentTool):
    name = "get_current_training_cycle"
    description = "Read the authenticated runner's one active cycle and bounded block structure."
    input_model = EmptyToolInput
    output_model = CurrentTrainingCycleOutput
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.WEEKLY_REVIEW,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    )

    def __init__(self, dependencies: CoachAgentToolDependencies, *, block_limit: int = 16) -> None:
        self.dependencies = dependencies
        self.block_limit = block_limit

    def execute(
        self, arguments: EmptyToolInput, context: AgentContext
    ) -> CurrentTrainingCycleOutput:
        del arguments
        cycle = self.dependencies.current_cycle(context.user_id)
        if cycle is None:
            return CurrentTrainingCycleOutput(data_status=TrainingDataStatus.NOT_FOUND)
        today = context.current_time.date()
        blocks = sorted(cycle.blocks, key=lambda item: (item.sort_order, item.id))
        current = next(
            (
                block
                for block in blocks
                if block.start_date is not None
                and block.end_date is not None
                and block.start_date <= today <= block.end_date
            ),
            None,
        )
        limitations = [
            _notice(
                "CYCLE_PROGRESS_UNAVAILABLE",
                "当前尚无可公开的确定性周期进度指标，因此不展示推测进度。",
            )
        ]
        if len(blocks) > self.block_limit:
            limitations.append(
                _notice("WEEKLY_STRUCTURE_TRIMMED", "训练周期块结构已按展示上限截取。")
            )
        return CurrentTrainingCycleOutput(
            data_status=TrainingDataStatus.AVAILABLE,
            cycle_id=cycle.id,
            name=_clean(cycle.name, 128),
            start_date=cycle.actual_start_date or cycle.start_date,
            end_date=cycle.actual_end_date or cycle.end_date,
            current_phase=_clean(current.phase_name, 128) if current else None,
            goal=_clean(cycle.goal, 255),
            progress=None,
            weekly_structure=[
                TrainingCycleBlockRead(
                    name=_clean(block.block_name, 128) or "未命名训练块",
                    start_date=block.start_date,
                    end_date=block.end_date,
                    phase=_clean(block.phase_name, 128),
                    focus=_clean(block.focus, 240),
                )
                for block in blocks[: self.block_limit]
            ],
            limitations=limitations,
        )
