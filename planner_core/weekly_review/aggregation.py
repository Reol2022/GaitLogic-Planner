from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any

from planner_core.weekly_review.enums import (
    DeviationSeverity,
    DeviationType,
    WeeklyClassificationStatus,
    WeeklyDataQualityLevel,
)
from planner_core.weekly_review.rules import (
    CANCELLED_STATUSES,
    COMPLETED_STATUSES,
    DISTANCE_OVER_RATIO,
    DISTANCE_UNDER_RATIO,
    EASY_TYPES,
    HARD_TYPES,
    KEY_TYPES,
    MODERATE_TYPES,
    WEEKLY_FACTS_VERSION,
    WEEKLY_RULES_VERSION,
)
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    RunnerStateSampleFact,
    RunnerStateTrend,
    WeeklyAdherenceMetrics,
    WeeklyClassification,
    WeeklyCompletedMetrics,
    WeeklyDataQuality,
    WeeklyDeviation,
    WeeklyDistributionMetrics,
    WeeklyFacts,
    WeeklyPeriod,
    WeeklyPlannedMetrics,
    WorkoutSessionFact,
)
from server.domain.decision_readiness import (
    DecisionReadiness,
    DomainReadiness,
    LimitationClass,
    classify_limitation,
    overall_readiness,
)


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _sum_present(values: list[float | None], digits: int = 2) -> float | None:
    present = [value for value in values if value is not None]
    return round(sum(present), digits) if present else None


def _ratio(numerator: float | int, denominator: float | int) -> float | None:
    return round(float(numerator) / float(denominator), 4) if denominator else None


def _trend(start: str, end: str, order: dict[str, int]) -> str:
    if start not in order or end not in order:
        return "UNKNOWN"
    if order[end] > order[start]:
        return "INCREASING"
    if order[end] < order[start]:
        return "DECREASING"
    return "STABLE"


def _state_trend(samples: list[RunnerStateSampleFact]) -> RunnerStateTrend:
    ordered = sorted(samples, key=lambda item: item.sample_date)
    if len(ordered) < 2:
        return RunnerStateTrend(
            sample_count=len(ordered),
            current_runner_state=(ordered[-1].load_trend if ordered else "UNKNOWN"),
            fatigue_level=(ordered[-1].fatigue_state if ordered else "UNKNOWN"),
        )
    first, last = ordered[0], ordered[-1]
    fatigue_order = {"NORMAL": 0, "ELEVATED": 1, "HIGH": 2}
    risk_order = {str(value): value for value in range(100)}
    return RunnerStateTrend(
        start_state=first.model_dump(mode="json"),
        end_state=last.model_dump(mode="json"),
        fatigue_trend=_trend(first.fatigue_state, last.fatigue_state, fatigue_order),
        load_trend=_trend(
            first.load_trend,
            last.load_trend,
            {"DECREASING": 0, "STABLE": 1, "INCREASING": 2, "SPIKING": 3},
        ),
        recovery_trend=_trend(
            first.recovery_state,
            last.recovery_state,
            {"GOOD": 0, "LIMITED": 1, "POOR": 2},
        ),
        risk_trend=_trend(
            str(first.risk_flag_count), str(last.risk_flag_count), risk_order
        ),
        current_runner_state=last.load_trend,
        fatigue_level=last.fatigue_state,
        sample_count=len(ordered),
    )


def _canonical_hash(payload: dict[str, Any]) -> str:
    stable = dict(payload)
    stable.pop("generated_at", None)
    stable.pop("result_hash", None)
    encoded = json.dumps(
        stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_weekly_facts(
    *,
    period: WeeklyPeriod,
    plans: list[PlannedSessionFact],
    logs: list[WorkoutSessionFact],
    runner_state_samples: list[RunnerStateSampleFact],
    as_of_date: date,
) -> WeeklyFacts:
    plans = sorted(
        (
            item
            for item in plans
            if period.week_start <= item.session_date <= min(period.week_end, as_of_date)
            and not item.is_cancelled
        ),
        key=lambda item: (item.session_date, item.plan_id or 0),
    )
    logs = sorted(
        (
            item
            for item in logs
            if period.week_start <= item.activity_date <= min(period.week_end, as_of_date)
        ),
        key=lambda item: (item.activity_date, item.log_id or 0),
    )
    plan_by_id = {item.plan_id: item for item in plans if item.plan_id is not None}
    matched_plan_ids: set[int] = set()
    matched: list[tuple[PlannedSessionFact | None, WorkoutSessionFact]] = []
    deviations: list[WeeklyDeviation] = []
    ambiguous_count = 0
    unmatched_count = 0
    fingerprints: set[str] = set()

    for log in logs:
        if log.activity_fingerprint and log.activity_fingerprint in fingerprints:
            deviations.append(
                WeeklyDeviation(
                    deviation_type=DeviationType.DUPLICATE_OR_AMBIGUOUS_LOG,
                    date=log.activity_date,
                    log_id=log.log_id,
                    severity=DeviationSeverity.WARNING,
                    evidence_codes=["DUPLICATE_ACTIVITY_FINGERPRINT"],
                )
            )
            ambiguous_count += 1
            continue
        if log.activity_fingerprint:
            fingerprints.add(log.activity_fingerprint)
        plan = plan_by_id.get(log.planned_workout_id)
        if plan is None and log.planned_workout_id is None:
            candidates = [
                item
                for item in plans
                if item.plan_id not in matched_plan_ids
                and item.session_date == log.activity_date
                and (
                    item.main_type == log.main_type
                    or "unknown" in {item.main_type, log.main_type}
                )
            ]
            if len(candidates) == 1:
                plan = candidates[0]
            elif len(candidates) > 1:
                ambiguous_count += 1
                deviations.append(
                    WeeklyDeviation(
                        deviation_type=DeviationType.DUPLICATE_OR_AMBIGUOUS_LOG,
                        date=log.activity_date,
                        log_id=log.log_id,
                        severity=DeviationSeverity.WARNING,
                        evidence_codes=["MULTIPLE_COMPATIBLE_PLANS"],
                    )
                )
                continue
        if plan is None:
            unmatched_count += 1
            deviations.append(
                WeeklyDeviation(
                    deviation_type=DeviationType.UNMATCHED_LOG,
                    date=log.activity_date,
                    log_id=log.log_id,
                    severity=DeviationSeverity.INFO,
                    actual={"main_type": log.main_type},
                    evidence_codes=["NO_UNIQUE_PLAN_MATCH"],
                )
            )
        elif plan.plan_id is not None:
            matched_plan_ids.add(plan.plan_id)
        matched.append((plan, log))

    completed_pairs = [
        pair for pair in matched if pair[1].status in COMPLETED_STATUSES
    ]
    partial_pairs = [
        pair for pair in completed_pairs if pair[1].status == "completed_adjusted"
    ]
    completed_plan_ids = {
        plan.plan_id
        for plan, _ in completed_pairs
        if plan is not None and plan.plan_id is not None
    }
    for plan in plans:
        if plan.main_type == "rest" or plan.plan_id in completed_plan_ids:
            continue
        kind = (
            DeviationType.KEY_SESSION_MISSED
            if plan.main_type in KEY_TYPES
            else DeviationType.MISSED_SESSION
        )
        if plan.main_type == "long_run":
            kind = DeviationType.LONG_RUN_MISSED
        deviations.append(
            WeeklyDeviation(
                deviation_type=kind,
                date=plan.session_date,
                plan_id=plan.plan_id,
                severity=(
                    DeviationSeverity.ATTENTION
                    if plan.main_type in KEY_TYPES
                    else DeviationSeverity.WARNING
                ),
                expected={"main_type": plan.main_type},
                evidence_codes=["NO_COMPLETED_LOG"],
            )
        )

    for plan, log in completed_pairs:
        if plan is None:
            deviations.append(
                WeeklyDeviation(
                    deviation_type=DeviationType.EXTRA_SESSION,
                    date=log.activity_date,
                    log_id=log.log_id,
                    severity=DeviationSeverity.INFO,
                    actual={"main_type": log.main_type},
                    evidence_codes=["COMPLETED_WITHOUT_PLAN"],
                )
            )
            continue
        if plan.distance_km and log.distance_km is not None:
            ratio = log.distance_km / plan.distance_km
            if ratio < DISTANCE_UNDER_RATIO or ratio > DISTANCE_OVER_RATIO:
                deviations.append(
                    WeeklyDeviation(
                        deviation_type=(
                            DeviationType.DISTANCE_UNDER
                            if ratio < DISTANCE_UNDER_RATIO
                            else DeviationType.DISTANCE_OVER
                        ),
                        date=log.activity_date,
                        plan_id=plan.plan_id,
                        log_id=log.log_id,
                        severity=DeviationSeverity.WARNING,
                        expected={"distance_km": plan.distance_km},
                        actual={"distance_km": log.distance_km},
                        evidence_codes=["DISTANCE_RATIO_OUTSIDE_BAND"],
                    )
                )
        if plan.duration_minutes and log.duration_minutes is not None:
            ratio = log.duration_minutes / plan.duration_minutes
            if ratio < DISTANCE_UNDER_RATIO or ratio > DISTANCE_OVER_RATIO:
                deviations.append(
                    WeeklyDeviation(
                        deviation_type=(
                            DeviationType.DURATION_UNDER
                            if ratio < DISTANCE_UNDER_RATIO
                            else DeviationType.DURATION_OVER
                        ),
                        date=log.activity_date,
                        plan_id=plan.plan_id,
                        log_id=log.log_id,
                        severity=DeviationSeverity.WARNING,
                        expected={"duration_minutes": plan.duration_minutes},
                        actual={"duration_minutes": log.duration_minutes},
                        evidence_codes=["DURATION_RATIO_OUTSIDE_BAND"],
                    )
                )
        if plan.main_type != log.main_type and log.main_type != "unknown":
            expected_rank = (
                2
                if plan.main_type in HARD_TYPES
                else 1
                if plan.main_type in MODERATE_TYPES
                else 0
            )
            actual_rank = (
                2
                if log.main_type in HARD_TYPES
                else 1
                if log.main_type in MODERATE_TYPES
                else 0
            )
            if expected_rank != actual_rank:
                deviations.append(
                    WeeklyDeviation(
                        deviation_type=(
                            DeviationType.INTENSITY_HIGHER_THAN_PLANNED
                            if actual_rank > expected_rank
                            else DeviationType.INTENSITY_LOWER_THAN_PLANNED
                        ),
                        date=log.activity_date,
                        plan_id=plan.plan_id,
                        log_id=log.log_id,
                        severity=DeviationSeverity.WARNING,
                        expected={"main_type": plan.main_type},
                        actual={"main_type": log.main_type},
                        evidence_codes=["MAIN_TYPE_MISMATCH"],
                    )
                )

    running_plans = [item for item in plans if item.main_type != "rest"]
    completed_logs = [log for _, log in completed_pairs]
    running_logs = [
        log for log in completed_logs if log.sport_type.lower() in {"run", "running"}
    ]
    planned_distance = _sum_present([item.distance_km for item in running_plans])
    actual_distance = _sum_present([item.distance_km for item in running_logs])
    planned_duration = _sum_present([item.duration_minutes for item in running_plans])
    actual_duration = _sum_present([item.duration_minutes for item in completed_logs])
    planned_keys = [item for item in running_plans if item.main_type in KEY_TYPES]
    planned_high_intensity = [
        item for item in running_plans if item.main_type in HARD_TYPES
    ]
    completed_keys = [
        (plan, log)
        for plan, log in completed_pairs
        if plan is not None and plan.main_type in KEY_TYPES
    ]
    completed_high_intensity = [
        (plan, log)
        for plan, log in completed_pairs
        if (plan.main_type if plan is not None else log.main_type) in HARD_TYPES
    ]
    planned_longs = [item for item in running_plans if item.main_type == "long_run"]
    completed_longs = [
        pair for pair in completed_keys if pair[0].main_type == "long_run"
    ]
    active_dates = {item.activity_date for item in running_logs}
    effective_days = (min(period.week_end, as_of_date) - period.week_start).days + 1

    buckets: dict[str, list[float | None]] = {
        "easy": [],
        "moderate": [],
        "hard": [],
        "unknown": [],
    }
    for plan, log in completed_pairs:
        main_type = plan.main_type if plan is not None else log.main_type
        bucket = (
            "easy"
            if main_type in EASY_TYPES
            else "moderate"
            if main_type in MODERATE_TYPES
            else "hard"
            if main_type in HARD_TYPES
            else "unknown"
        )
        buckets[bucket].append(
            log.distance_km
            if log.sport_type.lower() in {"run", "running"}
            else None
        )
    bucket_totals = {key: _sum_present(value) for key, value in buckets.items()}
    known_total = sum(value or 0 for value in bucket_totals.values())
    distribution = WeeklyDistributionMetrics(
        easy_distance_km=bucket_totals["easy"],
        moderate_distance_km=bucket_totals["moderate"],
        hard_distance_km=bucket_totals["hard"],
        unknown_intensity_distance_km=bucket_totals["unknown"],
        easy_ratio=_ratio(bucket_totals["easy"] or 0, known_total),
        moderate_ratio=_ratio(bucket_totals["moderate"] or 0, known_total),
        hard_ratio=_ratio(bucket_totals["hard"] or 0, known_total),
    )

    missing_fields: set[str] = set()
    if any(item.distance_km is None for item in running_plans):
        missing_fields.add("planned_distance_km")
    if any(item.distance_km is None for item in running_logs):
        missing_fields.add("actual_distance_km")
    if any(item.duration_minutes is None for item in completed_logs):
        missing_fields.add("actual_duration_minutes")
    trend = _state_trend(runner_state_samples)
    if ambiguous_count:
        quality = WeeklyDataQualityLevel.CONFLICTED
    elif not plans and not logs:
        quality = WeeklyDataQualityLevel.INSUFFICIENT
    elif missing_fields or unmatched_count or trend.sample_count < 2:
        quality = WeeklyDataQualityLevel.PARTIAL
    else:
        quality = WeeklyDataQualityLevel.COMPLETE

    adherence = WeeklyAdherenceMetrics(
        session_completion_rate=_ratio(len(completed_plan_ids), len(running_plans)),
        distance_completion_rate=(
            _ratio(actual_distance or 0, planned_distance)
            if planned_distance is not None
            else None
        ),
        key_session_completion_rate=_ratio(len(completed_keys), len(planned_keys)),
        long_run_completion_rate=_ratio(len(completed_longs), len(planned_longs)),
    )
    statuses: list[WeeklyClassificationStatus] = []
    rules: list[str] = []
    warnings: list[str] = []
    limitations: list[str] = []
    # A missing plan limits plan-adherence only; completed training facts can
    # still support a partial weekly review.
    if not running_plans and not logs:
        statuses.append(WeeklyClassificationStatus.INSUFFICIENT_DATA)
        rules.append("NO_PLANNED_RUNNING_SESSIONS")
    elif quality == WeeklyDataQualityLevel.INSUFFICIENT and not logs:
        statuses.append(WeeklyClassificationStatus.INSUFFICIENT_DATA)
        rules.append("WEEKLY_DATA_INSUFFICIENT")
    if (
        adherence.distance_completion_rate is not None
        and adherence.distance_completion_rate < DISTANCE_UNDER_RATIO
    ):
        statuses.append(WeeklyClassificationStatus.UNDER_COMPLETED)
        rules.append("DISTANCE_COMPLETION_BELOW_0_80")
    if (
        adherence.distance_completion_rate is not None
        and adherence.distance_completion_rate > DISTANCE_OVER_RATIO
    ):
        statuses.append(WeeklyClassificationStatus.OVER_COMPLETED)
        rules.append("DISTANCE_COMPLETION_ABOVE_1_20")
    if any(
        item.deviation_type
        in {
            DeviationType.INTENSITY_HIGHER_THAN_PLANNED,
            DeviationType.INTENSITY_LOWER_THAN_PLANNED,
        }
        for item in deviations
    ):
        statuses.append(WeeklyClassificationStatus.INTENSITY_IMBALANCE)
        rules.append("PLANNED_ACTUAL_INTENSITY_MISMATCH")
    if any(
        item.fatigue_state in {"ELEVATED", "HIGH"} or item.risk_flag_count > 0
        for item in runner_state_samples
    ):
        statuses.append(WeeklyClassificationStatus.RECOVERY_CONCERN)
        rules.append("RUNNER_STATE_RECOVERY_SIGNAL")
        warnings.append("已有 Runner State 显示恢复或风险关注信号。")
    if not statuses and quality != WeeklyDataQualityLevel.INSUFFICIENT:
        statuses.append(WeeklyClassificationStatus.ON_TRACK)
        rules.append("NO_MATERIAL_WEEKLY_DEVIATION")
    unique_statuses = list(dict.fromkeys(statuses))
    if len(unique_statuses) > 1:
        primary = WeeklyClassificationStatus.MIXED
        secondary = unique_statuses
    else:
        primary = unique_statuses[0]
        secondary = []
    if trend.sample_count < 2:
        limitations.append("INSUFFICIENT_RUNNER_STATE_HISTORY")
    if planned_duration is None:
        limitations.append("PLANNED_DURATION_NOT_STRUCTURED")
    if missing_fields:
        limitations.append("SOME_METRICS_EXCLUDE_MISSING_VALUES")

    domains = [
        DomainReadiness(domain="plan_execution", readiness=DecisionReadiness.READY if running_plans else DecisionReadiness.BLOCKED),
        DomainReadiness(domain="training_volume", readiness=DecisionReadiness.READY if logs else DecisionReadiness.BLOCKED),
        DomainReadiness(domain="training_frequency", readiness=DecisionReadiness.READY if logs else DecisionReadiness.BLOCKED),
        DomainReadiness(domain="key_session_completion", readiness=DecisionReadiness.READY if planned_keys or completed_keys else DecisionReadiness.NOT_APPLICABLE),
        DomainReadiness(domain="intensity_distribution", readiness=DecisionReadiness.PARTIAL if missing_fields else DecisionReadiness.READY),
        DomainReadiness(domain="long_run", readiness=DecisionReadiness.READY if planned_longs or completed_longs else DecisionReadiness.NOT_APPLICABLE),
        DomainReadiness(domain="recovery", readiness=DecisionReadiness.PARTIAL if missing_fields else DecisionReadiness.NOT_APPLICABLE),
        DomainReadiness(domain="subjective_fatigue", readiness=DecisionReadiness.BLOCKED),
        DomainReadiness(domain="training_phase", readiness=DecisionReadiness.BLOCKED if not period.training_phase else DecisionReadiness.READY),
    ]

    missed_plan_ids = {
        item.plan_id
        for item in deviations
        if item.plan_id is not None
        and item.deviation_type
        in {
            DeviationType.MISSED_SESSION,
            DeviationType.KEY_SESSION_MISSED,
            DeviationType.LONG_RUN_MISSED,
        }
    }
    extra_log_ids = {
        item.log_id
        for item in deviations
        if item.log_id is not None and item.deviation_type == DeviationType.EXTRA_SESSION
    }
    evidence_codes = list(
        dict.fromkeys(
            code
            for deviation in deviations
            for code in deviation.evidence_codes
        )
    )

    generated_at = datetime.now(timezone.utc)
    result = WeeklyFacts(
        period=period,
        planned=WeeklyPlannedMetrics(
            planned_session_count=len(plans),
            planned_running_session_count=len(running_plans),
            planned_distance_km=planned_distance,
            planned_duration_minutes=planned_duration,
            planned_key_session_count=len(planned_keys),
            planned_high_intensity_session_count=len(planned_high_intensity),
            planned_long_run_count=len(planned_longs),
            planned_rest_days=len({item.session_date for item in plans if item.main_type == "rest"}),
        ),
        completed=WeeklyCompletedMetrics(
            completed_session_count=len(completed_logs),
            completed_running_session_count=len(running_logs),
            actual_distance_km=actual_distance,
            actual_duration_minutes=actual_duration,
            completed_key_session_count=len(completed_keys),
            completed_high_intensity_session_count=len(completed_high_intensity),
            completed_long_run_count=len(completed_longs),
            partial_session_count=len(partial_pairs),
            missed_session_count=len(missed_plan_ids),
            extra_session_count=len(extra_log_ids),
            actual_rest_days=max(0, effective_days - len(active_dates)),
        ),
        adherence=adherence,
        distribution=distribution,
        deviations=deviations,
        runner_state_trend=trend,
        data_quality=WeeklyDataQuality(
            level=quality,
            missing_plan_days=sorted(
                {
                    log.activity_date
                    for plan, log in matched
                    if plan is None
                    and log.activity_date <= min(period.week_end, as_of_date)
                }
            ),
            missing_log_fields=sorted(missing_fields),
            unmatched_log_count=unmatched_count,
            ambiguous_match_count=ambiguous_count,
            runner_state_sample_count=trend.sample_count,
        ),
        classification=WeeklyClassification(
            primary_status=primary,
            secondary_statuses=secondary,
            rule_codes=rules,
            evidence_codes=evidence_codes,
            warnings=warnings,
            limitations=limitations,
            overall_readiness=overall_readiness(domains).value,
            domain_readiness=[item.model_dump(mode="json") for item in domains],
            hard_blockers=(
                []
                if logs or running_plans
                else ["WEEKLY_CORE_FACTS_UNAVAILABLE"]
            ),
            data_limitations=[
                item
                for item in limitations
                if classify_limitation(item) == LimitationClass.SOFT_LIMITATION
            ],
            capability_limitations=[
                item
                for item in limitations
                if classify_limitation(item) == LimitationClass.CAPABILITY_LIMITATION
            ],
        ),
        weekly_facts_version=WEEKLY_FACTS_VERSION,
        rules_version=WEEKLY_RULES_VERSION,
        result_hash="",
        generated_at=generated_at,
    )
    result.result_hash = _canonical_hash(result.model_dump(mode="json"))
    return result
