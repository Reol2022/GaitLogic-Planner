from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, pstdev

from planner_core.database.models import PlannedWorkout, TrainingCycle, WorkoutLog
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES
from server.domain.runner_state_rules import RunnerStateRules
from server.domain.decision_readiness import assess_runner_state_domains, classify_limitation, overall_readiness
from server.schemas.runner_state import (
    FatigueInference,
    FatigueState,
    InferenceBasis,
    InferenceEvidence,
    ReasonCode,
    RiskFlagCode,
    RiskSeverity,
    RunnerStateDerivedMetrics,
    RunnerStateInferenceMetadata,
    RunnerStateRiskFlag,
    RunnerStateSnapshot,
    SuggestedActionType,
    TrainingConsistencyInference,
    TrainingConsistencyState,
    TrainingPhaseState,
    VolumeTrendInference,
    VolumeTrendState,
    WeeklyTrainingBreakdown,
)
from server.services.runner_state_rules_loader import get_runner_state_rules
from server.services.runner_state_service import (
    _completion_rate,
    _deduplicate_log_rows,
    _effective_date,
    _effective_type,
    _valid_nonnegative,
    _window_metrics,
)
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, REST_STATUSES

RECENT_WINDOW = "recent_7d"
BASELINE_WINDOW = "previous_21d"
FULL_WINDOW = "full_28d"
SOURCE = "runner_state_foundation"
FATIGUE_SIGNAL_NAMES = (
    "VOLUME_CHANGE",
    "RPE_CHANGE",
    "PLAN_COMPLETION_CHANGE",
    "CONSECUTIVE_HIGH_INTENSITY_DAYS",
    "FREQUENT_HIGH_INTENSITY_SESSIONS",
)


def _evidence(
    metric: str,
    value: float | int | str | None,
    *,
    threshold: float | int | str | None,
    unit: str | None,
    window: str,
    used: bool = True,
) -> InferenceEvidence:
    return InferenceEvidence(
        metric=metric,
        value=value,
        threshold=threshold,
        unit=unit,
        window=window,
        source=SOURCE,
        used=used,
    )


def _valid_completed_rows(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]], start: date, end: date
) -> list[tuple[WorkoutLog, PlannedWorkout | None]]:
    result: list[tuple[WorkoutLog, PlannedWorkout | None]] = []
    for row in rows:
        log, _ = row
        day = _effective_date(*row)
        if day is None or not start <= day <= end:
            continue
        if log.status_normalized not in COMPLETED_STATUSES or log.status_normalized in REST_STATUSES:
            continue
        if _effective_type(*row).value == "rest":
            continue
        if _valid_nonnegative(log.actual_distance_km) is None and _valid_nonnegative(log.actual_duration_seconds) is None:
            continue
        result.append(row)
    return result


def _weekly_breakdown(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]], start_28d: date
) -> list[WeeklyTrainingBreakdown]:
    """Return four non-overlapping seven-natural-day buckets, oldest first."""
    result: list[WeeklyTrainingBreakdown] = []
    for index in range(4):
        start = start_28d + timedelta(days=index * 7)
        end = start + timedelta(days=6)
        valid_rows = _valid_completed_rows(rows, start, end)
        distances = [
            distance
            for log, _ in valid_rows
            if (distance := _valid_nonnegative(log.actual_distance_km)) is not None
        ]
        result.append(
            WeeklyTrainingBreakdown(
                window_start=start,
                window_end=end,
                distance_km=round(sum(distances), 2) if distances else None,
                sessions=len(valid_rows),
                active=bool(valid_rows),
            )
        )
    return result


def _high_intensity_dates(
    rows: list[tuple[WorkoutLog, PlannedWorkout | None]], start: date, end: date
) -> list[date]:
    dates: list[date] = []
    for row in rows:
        log, _ = row
        day = _effective_date(*row)
        if day is None or not start <= day <= end or log.status_normalized not in COMPLETED_STATUSES:
            continue
        if _effective_type(*row).value in HIGH_INTENSITY_TYPES:
            dates.append(day)
    return dates


def _maximum_consecutive_days(days: list[date]) -> int:
    unique_days = sorted(set(days))
    maximum = current = 0
    previous: date | None = None
    for day in unique_days:
        current = current + 1 if previous is not None and day == previous + timedelta(days=1) else 1
        maximum = max(maximum, current)
        previous = day
    return maximum


def derive_metrics(
    snapshot: RunnerStateSnapshot,
    log_rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
    planned_workouts: list[PlannedWorkout],
) -> RunnerStateDerivedMetrics:
    end = snapshot.identity.calculation_window_end
    start_28d = snapshot.identity.calculation_window_start_28d
    start_previous = start_28d
    end_previous = end - timedelta(days=7)
    rows = _deduplicate_log_rows(log_rows)
    previous = _window_metrics(rows, planned_workouts, start_previous, end_previous)
    weeks = _weekly_breakdown(rows, start_28d)
    weekly_sessions = [item.sessions for item in weeks]
    weekly_mean = mean(weekly_sessions)
    weekly_cv = round(pstdev(weekly_sessions) / weekly_mean, 4) if weekly_mean else None
    high_7d_dates = _high_intensity_dates(rows, snapshot.identity.calculation_window_start_7d, end)
    high_28d_dates = _high_intensity_dates(rows, start_28d, end)
    return RunnerStateDerivedMetrics(
        calculation_window_start_previous_21d=start_previous,
        calculation_window_end_previous_21d=end_previous,
        distance_previous_21d_km=previous.distance_km,
        sessions_previous_21d=previous.sessions,
        valid_workout_count_previous_21d=previous.valid_workout_count,
        average_rpe_previous_21d=previous.average_rpe,
        rpe_coverage_previous_21d=previous.rpe_coverage,
        planned_sessions_previous_21d=previous.planned_sessions,
        completed_planned_sessions_previous_21d=previous.completed_planned_sessions,
        completion_rate_previous_21d=_completion_rate(previous),
        active_weeks_previous_21d=sum(item.active for item in weeks[:3]),
        active_weeks_28d=sum(item.active for item in weeks),
        weekly_distance_breakdown_28d=weeks,
        weekly_session_breakdown_28d=weeks,
        weekly_session_mean_28d=round(weekly_mean, 2),
        weekly_session_cv_28d=weekly_cv,
        high_intensity_sessions_7d=len(high_7d_dates),
        high_intensity_sessions_28d=len(high_28d_dates),
        maximum_consecutive_high_intensity_days_7d=_maximum_consecutive_days(high_7d_dates),
    )


def infer_volume_trend(
    snapshot: RunnerStateSnapshot, derived: RunnerStateDerivedMetrics, rules: RunnerStateRules
) -> VolumeTrendInference:
    reasons: list[ReasonCode] = []
    recent = snapshot.recent_training.distance_7d_km
    baseline_total = derived.distance_previous_21d_km
    weekly_baseline = round(baseline_total / 3, 4) if baseline_total is not None else None
    enough_global = (
        snapshot.data_quality.valid_workout_count_28d >= rules.data_sufficiency.minimum_valid_workouts_28d
        and derived.active_weeks_28d >= rules.data_sufficiency.minimum_active_weeks_28d
    )
    enough_baseline = (
        derived.valid_workout_count_previous_21d >= rules.data_sufficiency.minimum_previous_21d_workouts
        and derived.active_weeks_previous_21d >= rules.data_sufficiency.minimum_previous_21d_active_weeks
    )
    if not enough_global:
        reasons.append(ReasonCode.INSUFFICIENT_DATA)
    if recent is None or baseline_total is None or weekly_baseline is None or weekly_baseline <= 0 or not enough_baseline:
        reasons.append(ReasonCode.INSUFFICIENT_BASELINE_DATA)
    if reasons:
        return VolumeTrendInference(
            state=VolumeTrendState.UNKNOWN,
            previous_21d_weekly_average_km=weekly_baseline,
            reason_codes=list(dict.fromkeys(reasons)),
            evidence=[
                _evidence("distance_7d_km", recent, threshold=None, unit="km", window=RECENT_WINDOW, used=False),
                _evidence(
                    "previous_21d_weekly_average_km",
                    weekly_baseline,
                    threshold="> 0",
                    unit="km/week",
                    window=BASELINE_WINDOW,
                    used=False,
                ),
            ],
            ruleset_version=rules.version,
        )

    ratio = round(recent / weekly_baseline, 4)
    if ratio < rules.volume_trend.decreasing_below:
        state, reason, threshold = (
            VolumeTrendState.DECREASING,
            ReasonCode.RECENT_VOLUME_BELOW_BASELINE,
            rules.volume_trend.decreasing_below,
        )
    elif ratio <= rules.volume_trend.stable_upper:
        state, reason, threshold = VolumeTrendState.STABLE, ReasonCode.RECENT_VOLUME_STABLE, rules.volume_trend.stable_upper
    elif ratio <= rules.volume_trend.increasing_upper:
        state, reason, threshold = (
            VolumeTrendState.INCREASING,
            ReasonCode.RECENT_VOLUME_ABOVE_BASELINE,
            rules.volume_trend.increasing_upper,
        )
    else:
        state, reason, threshold = VolumeTrendState.SPIKING, ReasonCode.RECENT_VOLUME_SPIKE, rules.volume_trend.increasing_upper
    return VolumeTrendInference(
        state=state,
        previous_21d_weekly_average_km=weekly_baseline,
        volume_ratio=ratio,
        reason_codes=[reason],
        evidence=[
            _evidence("distance_7d_km", recent, threshold=None, unit="km", window=RECENT_WINDOW),
            _evidence("previous_21d_weekly_average_km", weekly_baseline, threshold="> 0", unit="km/week", window=BASELINE_WINDOW),
            _evidence("volume_ratio", ratio, threshold=threshold, unit="ratio", window=f"{RECENT_WINDOW}_vs_{BASELINE_WINDOW}"),
        ],
        ruleset_version=rules.version,
    )


def infer_training_consistency(
    snapshot: RunnerStateSnapshot, derived: RunnerStateDerivedMetrics, rules: RunnerStateRules
) -> TrainingConsistencyInference:
    enough_global = (
        snapshot.data_quality.valid_workout_count_28d >= rules.data_sufficiency.minimum_valid_workouts_28d
        and derived.active_weeks_28d >= rules.data_sufficiency.minimum_active_weeks_28d
    )
    if not enough_global:
        return TrainingConsistencyInference(
            reason_codes=[ReasonCode.INSUFFICIENT_DATA],
            ruleset_version=rules.version,
        )

    planned = snapshot.recent_training.planned_sessions_28d
    completion = snapshot.recent_training.completion_rate_28d
    if planned >= rules.data_sufficiency.minimum_planned_sessions_for_consistency and completion is not None:
        basis = InferenceBasis.PLAN_COMPLETION
        if completion >= rules.consistency.high_completion_rate and derived.active_weeks_28d == rules.consistency.high_active_weeks:
            state, reason = TrainingConsistencyState.HIGH, ReasonCode.HIGH_PLAN_COMPLETION
        elif completion >= rules.consistency.moderate_completion_rate and derived.active_weeks_28d >= rules.consistency.moderate_active_weeks:
            state, reason = TrainingConsistencyState.MODERATE, ReasonCode.MODERATE_PLAN_COMPLETION
        else:
            state, reason = TrainingConsistencyState.LOW, ReasonCode.LOW_PLAN_COMPLETION
        evidence = [
            _evidence("completion_rate_28d", completion, threshold=rules.consistency.high_completion_rate, unit="ratio", window=FULL_WINDOW),
            _evidence("active_weeks_28d", derived.active_weeks_28d, threshold=rules.consistency.high_active_weeks, unit="weeks", window=FULL_WINDOW),
        ]
    else:
        basis = InferenceBasis.ACTIVITY_REGULARITY
        active = derived.active_weeks_28d
        average = derived.weekly_session_mean_28d
        cv = derived.weekly_session_cv_28d
        if active == rules.consistency.high_active_weeks and average >= rules.consistency.minimum_average_sessions_per_week_for_high and cv is not None and cv <= rules.consistency.high_weekly_session_cv:
            state, reason = TrainingConsistencyState.HIGH, ReasonCode.STABLE_ACTIVITY_FREQUENCY
        elif active >= rules.consistency.moderate_active_weeks and cv is not None and cv <= rules.consistency.moderate_weekly_session_cv:
            state, reason = TrainingConsistencyState.MODERATE, ReasonCode.MODERATE_ACTIVITY_FREQUENCY
        elif active >= rules.data_sufficiency.minimum_active_weeks_28d:
            state, reason = TrainingConsistencyState.LOW, ReasonCode.UNSTABLE_ACTIVITY_FREQUENCY
        else:
            return TrainingConsistencyInference(
                basis=basis,
                reason_codes=[ReasonCode.INSUFFICIENT_DATA, ReasonCode.INSUFFICIENT_PLAN_DATA],
                ruleset_version=rules.version,
            )
        evidence = [
            _evidence("active_weeks_28d", active, threshold=rules.consistency.moderate_active_weeks, unit="weeks", window=FULL_WINDOW),
            _evidence("weekly_session_mean_28d", average, threshold=rules.consistency.minimum_average_sessions_per_week_for_high, unit="sessions/week", window=FULL_WINDOW),
            _evidence("weekly_session_cv_28d", cv, threshold=rules.consistency.moderate_weekly_session_cv, unit="cv", window=FULL_WINDOW),
        ]
    return TrainingConsistencyInference(
        state=state,
        basis=basis,
        reason_codes=[reason],
        evidence=evidence,
        evidence_coverage=1.0,
        ruleset_version=rules.version,
    )


def infer_fatigue(
    snapshot: RunnerStateSnapshot,
    derived: RunnerStateDerivedMetrics,
    volume: VolumeTrendInference,
    rules: RunnerStateRules,
) -> FatigueInference:
    score = 0
    available = 0
    triggered: list[str] = []
    skipped: list[str] = []
    reasons: list[ReasonCode] = []
    evidence: list[InferenceEvidence] = []

    if volume.state is VolumeTrendState.UNKNOWN:
        skipped.append(FATIGUE_SIGNAL_NAMES[0])
    else:
        available += 1
        points = 2 if volume.state is VolumeTrendState.SPIKING else 1 if volume.state is VolumeTrendState.INCREASING else 0
        if points:
            score += points
            triggered.append(FATIGUE_SIGNAL_NAMES[0])
            reasons.append(ReasonCode.VOLUME_INCREASE_SIGNAL)
        evidence.append(_evidence("volume_trend", volume.state.value, threshold="INCREASING", unit="state", window=RECENT_WINDOW))

    recent_rpe = snapshot.recent_training.average_rpe_7d
    baseline_rpe = derived.average_rpe_previous_21d
    rpe_available = (
        recent_rpe is not None
        and baseline_rpe is not None
        and snapshot.data_quality.rpe_coverage_7d >= rules.data_sufficiency.minimum_rpe_coverage
        and derived.rpe_coverage_previous_21d >= rules.data_sufficiency.minimum_rpe_coverage
    )
    if not rpe_available:
        skipped.append(FATIGUE_SIGNAL_NAMES[1])
        reasons.append(ReasonCode.INSUFFICIENT_RPE_COVERAGE)
    else:
        available += 1
        delta = round(recent_rpe - baseline_rpe, 2)
        if delta >= rules.fatigue.rpe_delta_high:
            score += 2
            triggered.append(FATIGUE_SIGNAL_NAMES[1])
            reasons.append(ReasonCode.RPE_INCREASE_SIGNAL)
        elif delta >= rules.fatigue.rpe_delta_moderate:
            score += 1
            triggered.append(FATIGUE_SIGNAL_NAMES[1])
            reasons.append(ReasonCode.RPE_INCREASE_SIGNAL)
        evidence.append(_evidence("average_rpe_delta", delta, threshold=rules.fatigue.rpe_delta_moderate, unit="RPE", window=f"{RECENT_WINDOW}_vs_{BASELINE_WINDOW}"))

    recent_completion = snapshot.recent_training.completion_rate_7d
    baseline_completion = derived.completion_rate_previous_21d
    if recent_completion is None or baseline_completion is None:
        skipped.append(FATIGUE_SIGNAL_NAMES[2])
        reasons.append(ReasonCode.INSUFFICIENT_PLAN_DATA)
    else:
        available += 1
        drop = round(baseline_completion - recent_completion, 4)
        if drop >= rules.fatigue.completion_rate_drop:
            score += 1
            triggered.append(FATIGUE_SIGNAL_NAMES[2])
            reasons.append(ReasonCode.COMPLETION_DROP_SIGNAL)
        evidence.append(_evidence("completion_rate_drop", drop, threshold=rules.fatigue.completion_rate_drop, unit="ratio", window=f"{RECENT_WINDOW}_vs_{BASELINE_WINDOW}"))

    enough_global = (
        snapshot.data_quality.valid_workout_count_28d >= rules.data_sufficiency.minimum_valid_workouts_28d
        and derived.active_weeks_28d >= rules.data_sufficiency.minimum_active_weeks_28d
    )
    if not enough_global:
        skipped.extend(FATIGUE_SIGNAL_NAMES[3:])
    else:
        available += 2
        consecutive = derived.maximum_consecutive_high_intensity_days_7d
        if consecutive >= rules.fatigue.consecutive_high_intensity_days:
            score += 2
            triggered.append(FATIGUE_SIGNAL_NAMES[3])
            reasons.append(ReasonCode.CONSECUTIVE_HIGH_INTENSITY_SIGNAL)
        evidence.append(_evidence("maximum_consecutive_high_intensity_days_7d", consecutive, threshold=rules.fatigue.consecutive_high_intensity_days, unit="days", window=RECENT_WINDOW))
        frequent = derived.high_intensity_sessions_7d
        if frequent >= rules.fatigue.frequent_high_intensity_sessions:
            score += 1
            triggered.append(FATIGUE_SIGNAL_NAMES[4])
            reasons.append(ReasonCode.FREQUENT_HIGH_INTENSITY_SIGNAL)
        evidence.append(_evidence("high_intensity_sessions_7d", frequent, threshold=rules.fatigue.frequent_high_intensity_sessions, unit="sessions", window=RECENT_WINDOW))

    coverage = round(available / len(FATIGUE_SIGNAL_NAMES), 4)
    if available < rules.data_sufficiency.minimum_available_fatigue_signals:
        state = FatigueState.UNKNOWN
        reasons.append(ReasonCode.INSUFFICIENT_FATIGUE_SIGNALS)
    elif score >= rules.fatigue.high_score:
        state = FatigueState.HIGH
    elif score >= rules.fatigue.elevated_score:
        state = FatigueState.ELEVATED
    else:
        state = FatigueState.NORMAL
    return FatigueInference(
        state=state,
        score=score,
        triggered_signals=triggered,
        skipped_signals=skipped,
        reason_codes=list(dict.fromkeys(reasons)),
        evidence=evidence,
        available_signal_count=available,
        evidence_coverage=coverage,
        ruleset_version=rules.version,
    )


def build_risk_flags(
    derived: RunnerStateDerivedMetrics,
    volume: VolumeTrendInference,
    fatigue: FatigueInference,
    rules: RunnerStateRules,
) -> list[RunnerStateRiskFlag]:
    evidence_by_metric = {item.metric: item for item in fatigue.evidence}
    flags: list[RunnerStateRiskFlag] = []
    if volume.state is VolumeTrendState.SPIKING:
        flags.append(RunnerStateRiskFlag(
            code=RiskFlagCode.VOLUME_SPIKE,
            severity=RiskSeverity.WARNING,
            message="近期跑量明显高于此前 21 天周均水平，建议复核训练安排与恢复情况。",
            suggested_action_type=SuggestedActionType.REVIEW_RECOVERY,
            triggered_rule="volume_ratio > increasing_upper",
            evidence=[item for item in volume.evidence if item.metric == "volume_ratio"],
        ))
    if derived.maximum_consecutive_high_intensity_days_7d >= rules.fatigue.consecutive_high_intensity_days:
        flags.append(RunnerStateRiskFlag(
            code=RiskFlagCode.CONSECUTIVE_HIGH_INTENSITY_DAYS,
            severity=RiskSeverity.ATTENTION,
            message="近期存在连续自然日高强度训练，建议人工复核恢复安排。",
            suggested_action_type=SuggestedActionType.ADD_RECOVERY,
            triggered_rule="maximum_consecutive_high_intensity_days_7d >= consecutive_high_intensity_days",
            evidence=[evidence_by_metric["maximum_consecutive_high_intensity_days_7d"]],
        ))
    if "RPE_CHANGE" in fatigue.triggered_signals:
        flags.append(RunnerStateRiskFlag(
            code=RiskFlagCode.RPE_ABOVE_BASELINE,
            severity=RiskSeverity.WARNING,
            message="近期有效 RPE 均值高于独立基线，建议复核主观用力感与恢复记录。",
            suggested_action_type=SuggestedActionType.REVIEW_RECOVERY,
            triggered_rule="average_rpe_delta >= rpe_delta_moderate",
            evidence=[evidence_by_metric["average_rpe_delta"]],
        ))
    if "PLAN_COMPLETION_CHANGE" in fatigue.triggered_signals:
        flags.append(RunnerStateRiskFlag(
            code=RiskFlagCode.RECENT_COMPLETION_DROP,
            severity=RiskSeverity.INFO,
            message="近期计划完成率低于此前 21 天，建议人工确认原因。",
            suggested_action_type=SuggestedActionType.MANUAL_CONFIRMATION,
            triggered_rule="completion_rate_previous_21d - completion_rate_7d >= completion_rate_drop",
            evidence=[evidence_by_metric["completion_rate_drop"]],
        ))
    if derived.high_intensity_sessions_7d >= rules.fatigue.frequent_high_intensity_sessions:
        flags.append(RunnerStateRiskFlag(
            code=RiskFlagCode.FREQUENT_HIGH_INTENSITY_SESSIONS,
            severity=RiskSeverity.INFO,
            message="近期高强度训练次数达到规则提示条件，建议复核训练密度。",
            suggested_action_type=SuggestedActionType.REVIEW,
            triggered_rule="high_intensity_sessions_7d >= frequent_high_intensity_sessions",
            evidence=[evidence_by_metric["high_intensity_sessions_7d"]],
        ))
    return flags


class RunnerStateInferenceService:
    def __init__(self, rules: RunnerStateRules | None = None) -> None:
        self.rules = rules or get_runner_state_rules()

    def infer(
        self,
        snapshot: RunnerStateSnapshot,
        *,
        log_rows: list[tuple[WorkoutLog, PlannedWorkout | None]],
        planned_workouts: list[PlannedWorkout],
        cycle: TrainingCycle | None,
    ) -> RunnerStateSnapshot:
        derived = derive_metrics(snapshot, log_rows, planned_workouts)
        volume = infer_volume_trend(snapshot, derived, self.rules)
        consistency = infer_training_consistency(snapshot, derived, self.rules)
        fatigue = infer_fatigue(snapshot, derived, volume, self.rules)
        risk_flags = build_risk_flags(derived, volume, fatigue, self.rules)

        # No structured cycle phase exists in the current model. Free-text phase_name
        # is deliberately not interpreted, and cycle timing is not used as a proxy.
        training_phase = TrainingPhaseState.UNKNOWN
        reason_codes = list(dict.fromkeys(
            [*volume.reason_codes, *consistency.reason_codes, *fatigue.reason_codes, ReasonCode.TRAINING_PHASE_UNAVAILABLE]
        ))
        limitations = set(snapshot.data_quality.limitations)
        limitations.update({
            "training_phase_unavailable_no_structured_cycle_phase",
            "recovery_day_fatigue_rule_disabled_v1",
            "near_zero_volume_baseline_cutoff_not_defined",
        })
        if any(item in snapshot.data_quality.limitations for item in ("composite_workout_intensity_segments_not_split",)):
            limitations.add("high_intensity_composite_segments_use_main_workout_type")
        inferred_state = snapshot.inferred_state.model_copy(update={
            "fatigue_state": fatigue.state,
            "training_consistency": consistency.state,
            "training_phase": training_phase,
            # fitness_state, load_trend, weaknesses and legacy risk_flags remain unchanged.
        })
        domain_readiness = assess_runner_state_domains(
            valid_workouts=snapshot.data_quality.valid_workout_count_28d,
            limitations=sorted(limitations),
        )
        return snapshot.model_copy(update={
            "inferred_state": inferred_state,
            "derived_metrics": derived,
            "volume_trend": volume,
            "training_consistency": consistency,
            "fatigue": fatigue,
            "risk_flags": risk_flags,
            "inference_metadata": RunnerStateInferenceMetadata(
                ruleset_version=self.rules.version,
                calculated_at=snapshot.identity.generated_at,
                reason_codes=reason_codes,
                limitations=sorted(limitations),
                overall_readiness=overall_readiness(domain_readiness).value,
                domain_readiness=[item.model_dump(mode="json") for item in domain_readiness],
                hard_blockers=[
                    item
                    for item in sorted(limitations)
                    if classify_limitation(item).value == "HARD_BLOCKER"
                ],
                data_limitations=[item for item in sorted(limitations) if classify_limitation(item).value == "SOFT_LIMITATION"],
                capability_limitations=[item for item in sorted(limitations) if classify_limitation(item).value == "CAPABILITY_LIMITATION"],
            ),
        })
