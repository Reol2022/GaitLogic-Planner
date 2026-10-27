from __future__ import annotations

from datetime import timedelta

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentNotice
from server.agent.tool import AgentTool
from server.agent.training_fact_consistency import check_recent_training_facts
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.schemas import (
    AgentDataQualityRead,
    RecentTrainingInput,
    RecentTrainingItem,
    RecentTrainingOutput,
    RecentTrainingSummary,
    TrainingDataQualityInput,
    TrainingDataQualityOutput,
    TrainingDataStatus,
)

_ALL_TRAINING_INTENTS = (
    AgentIntent.TODAY_RECOMMENDATION,
    AgentIntent.WEEKLY_REVIEW,
    AgentIntent.EXPLAIN_RUNNER_STATE,
    AgentIntent.GENERAL_TRAINING_QUESTION,
    AgentIntent.PERSONAL_TRAINING_ANALYSIS,
    AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
    AgentIntent.PERSONAL_TRAINING_STATUS,
)


def _notice(code: str, message: str) -> AgentNotice:
    return AgentNotice(code=code, message=message)


class GetRecentTrainingTool(AgentTool):
    name = "get_recent_training"
    description = "Read bounded normalized recent workout facts for the authenticated runner."
    input_model = RecentTrainingInput
    output_model = RecentTrainingOutput
    allowed_intents = _ALL_TRAINING_INTENTS
    provided_fact_domains = (
        "training_volume",
        "training_frequency",
        "recent_intensity",
        "training_load",
        "plan_execution",
        "subjective_fatigue",
    )

    def __init__(self, dependencies: CoachAgentToolDependencies, *, item_limit: int = 20) -> None:
        self.dependencies = dependencies
        self.item_limit = item_limit

    def execute(self, arguments: RecentTrainingInput, context: AgentContext) -> RecentTrainingOutput:
        limit = min(arguments.limit, self.item_limit)
        as_of_date = arguments.end_date or context.current_time.date()
        days = arguments.days or 7
        recent = self.dependencies.recent_training(
            context.user_id,
            days,
            limit,
            as_of_date=as_of_date,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
        )
        range_start = recent.start_date or (recent.as_of_date - timedelta(days=recent.window_days - 1))
        range_end = recent.end_date or recent.as_of_date
        quality = self.dependencies.training_data_quality(
            context.user_id,
            recent.window_days,
            as_of_date=as_of_date,
            start_date=range_start,
            end_date=range_end,
        )
        if not recent.items:
            data_status = TrainingDataStatus.NOT_FOUND
        elif quality.missing_fields:
            data_status = TrainingDataStatus.PARTIAL
        else:
            data_status = TrainingDataStatus.AVAILABLE
        completeness = (
            round(sum(quality.coverage.values()) / len(quality.coverage), 4)
            if quality.coverage
            else 0.0
        )
        details_complete, issues = check_recent_training_facts(recent, visible_limit=limit)
        return RecentTrainingOutput(
            data_status=data_status,
            as_of=recent.as_of_date,
            range_start=range_start,
            range_end=range_end,
            range_kind=arguments.range_kind or f"ROLLING_{recent.window_days}_DAYS",
            range_label=arguments.range_label or f"最近 {recent.window_days} 天",
            items=[
                RecentTrainingItem.model_validate(
                    item.model_dump(exclude={"is_key_session"})
                )
                for item in recent.items[:limit]
            ],
            details_complete=details_complete,
            summary=RecentTrainingSummary(
                total_sessions=recent.total_sessions,
                total_distance_km=recent.total_distance_km,
                completed_key_sessions=recent.completed_key_sessions,
                rest_days=recent.rest_days,
                planned_sessions_due=recent.planned_sessions_due,
                completed_planned_sessions=recent.completed_planned_sessions,
                unplanned_sessions=recent.unplanned_sessions,
                completion_rate=recent.completion_rate,
            ),
            fact_issues=issues,
            data_quality=AgentDataQualityRead(
                level=("NONE" if quality.valid_workout_count == 0 else "PARTIAL" if quality.missing_fields else "COMPLETE"),
                completeness=completeness,
                missing_fields=quality.missing_fields,
            ),
            missing_reasons=(
                ["No workout logs were found in the requested window."]
                if not recent.items
                else [f"Incomplete field coverage: {name}." for name in quality.missing_fields]
            ),
        )


class GetTrainingDataQualityTool(AgentTool):
    name = "get_training_data_quality"
    description = "Read data-completeness coverage without interpreting missing fields as risk."
    input_model = TrainingDataQualityInput
    output_model = TrainingDataQualityOutput
    allowed_intents = _ALL_TRAINING_INTENTS
    provided_fact_domains = ("data_quality",)

    def __init__(self, dependencies: CoachAgentToolDependencies) -> None:
        self.dependencies = dependencies

    def execute(
        self, arguments: TrainingDataQualityInput, context: AgentContext
    ) -> TrainingDataQualityOutput:
        quality = self.dependencies.training_data_quality(
            context.user_id,
            arguments.window_days,
            as_of_date=arguments.end_date or context.current_time.date(),
            start_date=arguments.start_date,
            end_date=arguments.end_date,
        )
        if quality.valid_workout_count == 0:
            status = TrainingDataStatus.UNKNOWN
            freshness = "NO_TRAINING_DATA"
        else:
            status = TrainingDataStatus.PARTIAL if quality.missing_fields else TrainingDataStatus.AVAILABLE
            freshness = (
                "UNKNOWN"
                if quality.freshness_days is None
                else "CURRENT"
                if quality.freshness_days <= 2
                else "STALE"
            )
        return TrainingDataQualityOutput(
            data_status=status,
            window_days=quality.window_days,
            coverage=quality.coverage,
            missing_fields=quality.missing_fields,
            source_mix=quality.source_mix,
            freshness=freshness,
            warnings=(
                [_notice("TRAINING_DATA_STALE", "最近一次已完成训练距今超过两天。")]
                if freshness == "STALE"
                else []
            ),
            limitations=[
                _notice(
                    "DATA_QUALITY_IS_COMPLETENESS",
                    "数据完整度只表示当前字段的可用情况，不代表医疗风险或模型置信度。",
                )
            ],
        )
