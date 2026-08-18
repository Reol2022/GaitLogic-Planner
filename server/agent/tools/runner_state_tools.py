from __future__ import annotations

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentNotice
from server.agent.tool import AgentTool
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.schemas import (
    AgentDataQualityRead,
    AgentEvidenceRead,
    EmptyToolInput,
    RunnerStateHistoryInput,
    RunnerStateHistoryItem,
    RunnerStateHistoryOutput,
    RunnerStateToolOutput,
    TrainingDataStatus,
)

_INTENTS = (
    AgentIntent.TODAY_RECOMMENDATION,
    AgentIntent.WEEKLY_REVIEW,
    AgentIntent.EXPLAIN_RUNNER_STATE,
    AgentIntent.GENERAL_TRAINING_QUESTION,
)


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _notice(code: str, message: str) -> AgentNotice:
    return AgentNotice(code=code, message=message[:300])


class GetRunnerStateTool(AgentTool):
    name = "get_runner_state"
    description = "Read the authenticated runner's current deterministic state summary."
    input_model = EmptyToolInput
    output_model = RunnerStateToolOutput
    allowed_intents = _INTENTS

    def __init__(self, dependencies: CoachAgentToolDependencies, *, evidence_limit: int = 5) -> None:
        self.dependencies = dependencies
        self.evidence_limit = evidence_limit

    def execute(self, arguments: EmptyToolInput, context: AgentContext) -> RunnerStateToolOutput:
        del arguments
        snapshot = self.dependencies.current_runner_state(context.user_id)
        quality = snapshot.data_quality
        level = _value(quality.data_quality_level)
        data_status = (
            TrainingDataStatus.UNKNOWN
            if level == "NONE"
            else TrainingDataStatus.PARTIAL
            if level in {"LOW", "MEDIUM"} or quality.missing_fields
            else TrainingDataStatus.AVAILABLE
        )
        evidence = []
        for section in (snapshot.volume_trend, snapshot.training_consistency, snapshot.fatigue):
            for item in (section.evidence if section is not None else [])[: self.evidence_limit]:
                evidence.append(AgentEvidenceRead.model_validate(item.model_dump()))
        risk_rank = {"INFO": 1, "WARNING": 2, "ATTENTION": 3}
        highest = max(
            (_value(flag.severity) for flag in snapshot.risk_flags),
            key=lambda item: risk_rank.get(item, 0),
            default=None,
        )
        risk_level = {
            "INFO": "LOW",
            "WARNING": "MODERATE",
            "ATTENTION": "HIGH",
        }.get(highest, "UNKNOWN" if level == "NONE" else "LOW")
        overall_state = _value(snapshot.fatigue.state) if snapshot.fatigue else "UNKNOWN"
        metrics = {
            **snapshot.recent_training.model_dump(mode="json"),
            "hard_distance_ratio_7d": snapshot.intensity.hard_distance_ratio_7d,
            "hard_distance_ratio_28d": snapshot.intensity.hard_distance_ratio_28d,
            "quality_sessions_7d": snapshot.intensity.quality_sessions_7d,
            "days_since_last_quality_session": snapshot.intensity.days_since_last_quality_session,
            "volume_trend": _value(snapshot.volume_trend.state) if snapshot.volume_trend else "UNKNOWN",
            "training_consistency": (
                _value(snapshot.training_consistency.state)
                if snapshot.training_consistency
                else "UNKNOWN"
            ),
            "training_phase": _value(snapshot.inferred_state.training_phase),
        }
        limitations = [
            _notice("RUNNER_STATE_LIMITATION", item)
            for item in [
                *quality.limitations,
                *(snapshot.inference_metadata.limitations if snapshot.inference_metadata else []),
            ][:20]
        ]
        return RunnerStateToolOutput(
            data_status=data_status,
            as_of_date=snapshot.identity.calculation_window_end,
            overall_state=overall_state,
            risk_level=risk_level,
            data_quality=AgentDataQualityRead(
                level=level,
                completeness=quality.confidence,
                missing_fields=quality.missing_fields[:30],
            ),
            metrics=metrics,
            evidence=evidence[: self.evidence_limit * 3],
            warnings=[
                _notice(f"RISK_{_value(flag.code)}", flag.message)
                for flag in snapshot.risk_flags[:20]
            ],
            limitations=limitations,
            overall_readiness=(snapshot.inference_metadata.overall_readiness if snapshot.inference_metadata else None),
            domain_readiness=(snapshot.inference_metadata.domain_readiness if snapshot.inference_metadata else []),
            hard_blockers=(snapshot.inference_metadata.hard_blockers if snapshot.inference_metadata else []),
            data_limitations=(snapshot.inference_metadata.data_limitations if snapshot.inference_metadata else []),
            capability_limitations=(snapshot.inference_metadata.capability_limitations if snapshot.inference_metadata else []),
        )


class GetRunnerStateHistoryTool(AgentTool):
    name = "get_runner_state_history"
    description = "Read bounded saved runner-state summaries without loading snapshot payloads."
    input_model = RunnerStateHistoryInput
    output_model = RunnerStateHistoryOutput
    allowed_intents = (AgentIntent.WEEKLY_REVIEW, AgentIntent.EXPLAIN_RUNNER_STATE)

    def __init__(self, dependencies: CoachAgentToolDependencies, *, history_limit: int = 7) -> None:
        self.dependencies = dependencies
        self.history_limit = history_limit

    def execute(
        self, arguments: RunnerStateHistoryInput, context: AgentContext
    ) -> RunnerStateHistoryOutput:
        limit = min(arguments.limit, self.history_limit)
        response = self.dependencies.runner_state_history(context.user_id, limit)
        items = [
            RunnerStateHistoryItem(
                snapshot_id=item.id,
                captured_at=item.created_at,
                trigger_type=_value(item.trigger_type),
                overall_state=item.fatigue_state or "UNKNOWN",
                risk_level="LOW" if item.risk_flag_count == 0 else "UNKNOWN",
                selected_metrics={
                    "distance_7d_km": item.distance_7d_km,
                    "distance_28d_km": item.distance_28d_km,
                    "volume_trend": item.volume_trend,
                    "training_consistency": item.training_consistency,
                    "training_phase": item.training_phase,
                    "risk_flag_count": item.risk_flag_count,
                },
                data_quality=item.data_completeness,
            )
            for item in response.items[:limit]
        ]
        limitations = []
        if any(item.risk_level == "UNKNOWN" for item in items):
            limitations.append(
                _notice(
                    "HISTORY_RISK_SEVERITY_UNAVAILABLE",
                    "History summaries store risk counts but not risk severity; no severity was inferred.",
                )
            )
        return RunnerStateHistoryOutput(
            data_status=(TrainingDataStatus.AVAILABLE if items else TrainingDataStatus.NOT_FOUND),
            items=items,
            trend_summary=(
                f"Returned {len(items)} saved snapshots in descending capture order."
                if items
                else None
            ),
            limitations=limitations,
        )
