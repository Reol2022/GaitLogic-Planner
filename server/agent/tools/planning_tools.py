from __future__ import annotations

from datetime import date, timedelta

from planner_core.enums import WorkoutMainTypeNormalized

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentNotice
from server.agent.tool import AgentTool
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.schemas import (
    CurrentTrainingCycleOutput,
    EmptyToolInput,
    TodayWorkoutOutput,
    WorkoutDateInput,
    TrainingCycleBlockRead,
    TrainingPlanWindowInput,
    TrainingPlanWindowItem,
    TrainingPlanWindowOutput,
    TrainingDataStatus,
)


def _clean(value: str | None, limit: int) -> str | None:
    cleaned = " ".join(value.split()) if value else ""
    return cleaned[:limit] or None


def _notice(code: str, message: str) -> AgentNotice:
    return AgentNotice(code=code, message=message)


class GetTodayWorkoutTool(AgentTool):
    name = "get_today_workout"
    description = "Read the authenticated runner's plan for today or one specified date; never change it."
    input_model = WorkoutDateInput
    output_model = TodayWorkoutOutput
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.GENERAL_TRAINING_QUESTION,
        AgentIntent.PERSONAL_TRAINING_ANALYSIS,
        AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
        AgentIntent.PERSONAL_TRAINING_FACT_QUERY,
    )
    provided_fact_domains = ("today_plan",)

    def __init__(self, dependencies: CoachAgentToolDependencies) -> None:
        self.dependencies = dependencies

    def execute(self, arguments: WorkoutDateInput, context: AgentContext) -> TodayWorkoutOutput:
        # Keep direct callers using the legacy EmptyToolInput compatible while
        # the registry exposes the newer optional target_date contract.
        target_date: date = getattr(arguments, "target_date", None) or context.current_time.date()
        today, cycle, workouts = self.dependencies.today_workouts(
            context.user_id, target_date=target_date
        )
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
        AgentIntent.PERSONAL_TRAINING_ANALYSIS,
        AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
    )
    provided_fact_domains = ("training_phase", "training_plan_context")

    def __init__(self, dependencies: CoachAgentToolDependencies, *, block_limit: int = 16) -> None:
        self.dependencies = dependencies
        self.block_limit = block_limit

    def execute(
        self, arguments: EmptyToolInput, context: AgentContext
    ) -> CurrentTrainingCycleOutput:
        del arguments
        lifecycle = self.dependencies.current_cycle_lifecycle(context.user_id)
        cycle = self.dependencies.current_cycle(context.user_id)
        if cycle is None:
            reference_cycle = lifecycle.latest_completed_cycle or lifecycle.next_cycle
            if reference_cycle is not None:
                return CurrentTrainingCycleOutput(
                    data_status=TrainingDataStatus.AVAILABLE,
                    lifecycle_status=lifecycle.state.value,
                    transition=lifecycle.transition,
                    cycle_id=reference_cycle.id,
                    name=_clean(reference_cycle.name, 128),
                    start_date=reference_cycle.actual_start_date or reference_cycle.start_date,
                    end_date=reference_cycle.actual_end_date or reference_cycle.end_date,
                    target_race_name=_clean(getattr(reference_cycle, "target_race_name", None), 128),
                    target_race_date=getattr(reference_cycle, "target_race_date", None),
                    goal=_clean(reference_cycle.goal, 255),
                    limitations=[
                        _notice(
                            "CYCLE_NOT_ACTIVE",
                            "This cycle is not active; it is provided only as recent training context.",
                        )
                    ],
                )
            return CurrentTrainingCycleOutput(
                data_status=TrainingDataStatus.NOT_FOUND,
                lifecycle_status=lifecycle.state.value,
                transition=lifecycle.transition,
            )
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
            lifecycle_status=lifecycle.state.value,
            transition=lifecycle.transition,
            cycle_id=cycle.id,
            name=_clean(cycle.name, 128),
            start_date=cycle.actual_start_date or cycle.start_date,
            end_date=cycle.actual_end_date or cycle.end_date,
            target_race_name=_clean(getattr(cycle, "target_race_name", None), 128),
            target_race_date=getattr(cycle, "target_race_date", None),
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


class GetTrainingPlanWindowTool(AgentTool):
    name = "get_training_plan_window"
    description = "Read a bounded future formal-plan window for the authenticated runner; never change it."
    input_model = TrainingPlanWindowInput
    output_model = TrainingPlanWindowOutput
    allowed_intents = (
        AgentIntent.PERSONAL_TRAINING_ANALYSIS,
        AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
    )
    provided_fact_domains = ("future_plan", "race_preparation")

    def __init__(self, dependencies: CoachAgentToolDependencies) -> None:
        self.dependencies = dependencies

    def execute(self, arguments: TrainingPlanWindowInput, context: AgentContext) -> TrainingPlanWindowOutput:
        range_end = arguments.end_date
        range_source = "USER_STATED_RACE_DATE"
        limitations: list[AgentNotice] = []
        if arguments.prefer_confirmed_race_date:
            cycle = self.dependencies.current_cycle(context.user_id)
            confirmed_race_date = getattr(cycle, "target_race_date", None) if cycle else None
            if (
                confirmed_race_date is not None
                and arguments.start_date <= confirmed_race_date <= arguments.start_date + timedelta(days=42)
            ):
                range_end = confirmed_race_date
                range_source = "CONFIRMED_CYCLE_RACE_DATE"
            elif confirmed_race_date is not None:
                limitations.append(_notice(
                    "CONFIRMED_RACE_OUTSIDE_PLAN_WINDOW",
                    "已确认的目标赛事日期超出本次有界计划查询范围，未来计划仍按用户本轮所述日期读取。",
                ))
        workouts = self.dependencies.planned_workouts(
            context.user_id,
            start_date=arguments.start_date,
            end_date=range_end,
        )
        return TrainingPlanWindowOutput(
            data_status=TrainingDataStatus.AVAILABLE if workouts else TrainingDataStatus.NOT_FOUND,
            range_start=arguments.start_date,
            range_end=range_end,
            range_source=range_source,
            items=[
                TrainingPlanWindowItem(
                    date=item.workout_date,
                    training_type=item.main_type_normalized.value,
                    title=_clean(item.planned_content, 160) or "未命名训练",
                    planned_distance_km=(float(item.planned_distance_km) if item.planned_distance_km is not None else None),
                    completion_status=(item.workout_log.status_normalized.value if item.workout_log else None),
                )
                for item in workouts
                if item.workout_date is not None
            ],
            limitations=limitations,
        )
