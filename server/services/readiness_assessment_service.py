from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin, PlannedWorkout, TrainingReadinessAssessment, WorkoutLog
from planner_core.enums import ReadinessDataQuality, TrainingStatus, WorkoutStatusNormalized
from server.common.exceptions import BadRequestError, NotFoundError
from server.domain import readiness_thresholds as thresholds
from server.domain.review_thresholds import KEY_WORKOUT_TYPES
from server.schemas.training_readiness import ReadinessSignal, TrainingReadinessAssessmentRead
from server.services.readiness_recommendation_service import build_recommendations
from server.services.training_load_service import build_training_load_summary
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, local_today


def _signal(dimension: str, key: str, level: str, message: str, evidence: dict[str, Any] | None = None) -> ReadinessSignal:
    return ReadinessSignal(
        dimension=dimension,
        signal_key=key,
        level=level,
        message=message,
        evidence=evidence or {},
    )


def _data_quality(summary) -> ReadinessDataQuality:
    if (
        summary.history_days < thresholds.MIN_HISTORY_DAYS_MEDIUM_QUALITY
        or summary.srpe_coverage_ratio < thresholds.LOW_SRPE_COVERAGE_RATIO
        or summary.recovery_checkin_coverage_ratio == 0
    ):
        return ReadinessDataQuality.low
    if (
        summary.history_days >= thresholds.MIN_HISTORY_DAYS_HIGH_QUALITY
        and summary.srpe_coverage_ratio >= thresholds.HIGH_SRPE_COVERAGE_RATIO
        and summary.recovery_checkin_coverage_ratio >= thresholds.HIGH_RECOVERY_COVERAGE_RATIO
    ):
        return ReadinessDataQuality.high
    return ReadinessDataQuality.medium


def _recent_checkins(db: Session, user_id: int, assessment_date: date) -> list[DailyRecoveryCheckin]:
    start = assessment_date - timedelta(days=6)
    return list(
        db.scalars(
            select(DailyRecoveryCheckin)
            .where(
                DailyRecoveryCheckin.user_id == user_id,
                DailyRecoveryCheckin.checkin_date >= start,
                DailyRecoveryCheckin.checkin_date <= assessment_date,
            )
            .order_by(DailyRecoveryCheckin.checkin_date)
        )
    )


def _recent_logs(db: Session, user_id: int, assessment_date: date) -> list[tuple[WorkoutLog, PlannedWorkout]]:
    start = assessment_date - timedelta(days=6)
    return list(
        db.execute(
            select(WorkoutLog, PlannedWorkout)
            .join(PlannedWorkout, PlannedWorkout.id == WorkoutLog.planned_workout_id)
            .where(
                WorkoutLog.user_id == user_id,
                PlannedWorkout.user_id == user_id,
                PlannedWorkout.workout_date >= start,
                PlannedWorkout.workout_date <= assessment_date,
            )
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
        )
    )


def _load_signals(summary) -> tuple[list[ReadinessSignal], list[ReadinessSignal]]:
    external: list[ReadinessSignal] = []
    internal: list[ReadinessSignal] = []
    if summary.distance_change_percentage is not None:
        if summary.distance_change_percentage >= thresholds.LOAD_CHANGE_MODERATE_PERCENT:
            external.append(
                _signal(
                    "external_load",
                    "rolling_distance_increase",
                    "moderate",
                    "最近 7 天跑量明显高于过去 28 天平均周跑量。",
                    {"distance_change_percentage": summary.distance_change_percentage},
                )
            )
        elif summary.distance_change_percentage >= thresholds.LOAD_CHANGE_WEAK_PERCENT:
            external.append(
                _signal(
                    "external_load",
                    "rolling_distance_increase",
                    "weak",
                    "最近 7 天跑量高于近期个人基线。",
                    {"distance_change_percentage": summary.distance_change_percentage},
                )
            )
    if summary.load_change_percentage is not None and summary.srpe_coverage_ratio >= thresholds.LOW_SRPE_COVERAGE_RATIO:
        if summary.load_change_percentage >= thresholds.SRPE_CHANGE_MODERATE_PERCENT:
            internal.append(
                _signal(
                    "internal_load",
                    "rolling_srpe_increase",
                    "moderate",
                    "最近 7 天 sRPE 负荷明显高于过去 28 天平均周负荷。",
                    {"load_change_percentage": summary.load_change_percentage},
                )
            )
        elif summary.load_change_percentage >= thresholds.SRPE_CHANGE_WEAK_PERCENT:
            internal.append(
                _signal(
                    "internal_load",
                    "rolling_srpe_increase",
                    "weak",
                    "最近 7 天 sRPE 负荷高于近期个人基线。",
                    {"load_change_percentage": summary.load_change_percentage},
                )
            )
    return external, internal


def _performance_and_internal_signals(rows: list[tuple[WorkoutLog, PlannedWorkout]]) -> tuple[list[ReadinessSignal], list[ReadinessSignal]]:
    internal: list[ReadinessSignal] = []
    performance: list[ReadinessSignal] = []
    key_rows = [
        (log, workout)
        for log, workout in rows
        if workout.main_type_normalized.value in KEY_WORKOUT_TYPES
        and log.status_normalized in COMPLETED_STATUSES
    ]
    high_rpes = [log.rpe for log, _ in key_rows if log.rpe is not None and log.rpe >= thresholds.KEY_WORKOUT_RPE_HIGH]
    if len(high_rpes) >= thresholds.HIGH_RPE_STREAK_COUNT:
        internal.append(
            _signal(
                "internal_load",
                "repeated_high_key_rpe",
                "moderate",
                "最近关键课 RPE 连续偏高。",
                {"count": len(high_rpes)},
            )
        )
    elif high_rpes:
        internal.append(
            _signal(
                "internal_load",
                "single_high_key_rpe",
                "weak",
                "最近有一次关键课 RPE 偏高。",
                {"count": len(high_rpes)},
            )
        )
    difficult = [
        log
        for log, workout in rows
        if workout.main_type_normalized.value in KEY_WORKOUT_TYPES
        and log.status_normalized in {WorkoutStatusNormalized.completed_adjusted, WorkoutStatusNormalized.missed}
    ]
    if len(difficult) >= 2:
        performance.append(
            _signal(
                "performance",
                "repeated_key_workout_difficulty",
                "moderate",
                "最近关键课多次降级或未完成。",
                {"count": len(difficult)},
            )
        )
    elif difficult:
        performance.append(
            _signal(
                "performance",
                "single_key_workout_difficulty",
                "weak",
                "最近有一次关键课降级或未完成。",
                {"count": len(difficult)},
            )
        )
    return internal, performance


def _recovery_signals(checkins: list[DailyRecoveryCheckin]) -> list[ReadinessSignal]:
    signals: list[ReadinessSignal] = []
    last_two = checkins[-2:]
    if len(last_two) >= 2 and all(item.sleep_quality is not None and item.sleep_quality <= thresholds.RECOVERY_LOW_VALUE for item in last_two):
        signals.append(_signal("recovery", "sleep_quality_decline", "moderate", "连续两天睡眠质量偏低。"))
    elif checkins and checkins[-1].sleep_quality is not None and checkins[-1].sleep_quality <= thresholds.RECOVERY_LOW_VALUE:
        signals.append(_signal("recovery", "single_low_sleep_quality", "weak", "最近一次睡眠质量偏低。"))
    for field, key, label, low_is_bad in (
        ("subjective_fatigue", "subjective_fatigue_high", "主观疲劳", False),
        ("muscle_soreness", "muscle_soreness_high", "肌肉酸痛", False),
        ("stress_level", "stress_level_high", "压力", False),
        ("leg_feeling", "leg_feeling_low", "腿感", True),
    ):
        values = [getattr(item, field) for item in last_two if getattr(item, field) is not None]
        if len(values) >= 2:
            bad = all(value <= thresholds.RECOVERY_LOW_VALUE for value in values) if low_is_bad else all(
                value >= thresholds.RECOVERY_HIGH_FATIGUE_VALUE for value in values
            )
            if bad:
                signals.append(_signal("recovery", key, "moderate", f"连续两天{label}状态偏差。"))
        elif values:
            bad = values[-1] <= thresholds.RECOVERY_LOW_VALUE if low_is_bad else values[-1] >= thresholds.RECOVERY_HIGH_FATIGUE_VALUE
            if bad:
                signals.append(_signal("recovery", key, "weak", f"最近一次{label}状态偏差。"))
    return signals


def _pain_signals(checkins: list[DailyRecoveryCheckin], rows: list[tuple[WorkoutLog, PlannedWorkout]]) -> list[ReadinessSignal]:
    signals: list[ReadinessSignal] = []
    latest = checkins[-1] if checkins else None
    if latest:
        if latest.pain_affects_gait:
            signals.append(_signal("pain", "pain_affects_gait", "strong", "疼痛已经影响步态，应优先保守处理。"))
        if latest.pain_level is not None and latest.pain_level >= thresholds.PAIN_STRONG_LEVEL:
            signals.append(_signal("pain", "high_pain_level", "strong", "恢复打卡记录到明显疼痛。", {"pain_level": latest.pain_level}))
        elif latest.pain_level is not None and latest.pain_level >= thresholds.PAIN_MODERATE_LEVEL:
            level = "strong" if latest.pain_trend.value == "worsening" else "moderate"
            signals.append(_signal("pain", "moderate_pain_level", level, "恢复打卡记录到需要关注的疼痛。", {"pain_level": latest.pain_level}))
        elif latest.pain_trend.value == "worsening":
            signals.append(_signal("pain", "pain_worsening", "moderate", "疼痛趋势正在加重。"))
    log_pain_values = [log.pain_level for log, _ in rows if log.pain_level is not None]
    if log_pain_values:
        max_log_pain = max(log_pain_values)
        if max_log_pain >= thresholds.PAIN_STRONG_LEVEL:
            signals.append(_signal("pain", "workout_log_high_pain", "strong", "训练日志记录到明显疼痛。", {"pain_level": max_log_pain}))
        elif max_log_pain >= thresholds.PAIN_MODERATE_LEVEL:
            signals.append(_signal("pain", "workout_log_moderate_pain", "moderate", "训练日志记录到需要关注的疼痛。", {"pain_level": max_log_pain}))
    return signals


def _decide_status(data_quality: ReadinessDataQuality, signals: list[ReadinessSignal], summary) -> TrainingStatus:
    if data_quality == ReadinessDataQuality.low and (
        summary.history_days < 7 or ("training_logs" in summary.missing_data and "recovery_checkins" in summary.missing_data)
    ):
        return TrainingStatus.insufficient_data
    strong = [signal for signal in signals if signal.level == "strong"]
    moderate = [signal for signal in signals if signal.level == "moderate"]
    moderate_dimensions = {signal.dimension for signal in moderate}
    has_pain_moderate = any(signal.dimension == "pain" and signal.level in {"moderate", "strong"} for signal in signals)
    if any(signal.signal_key == "pain_affects_gait" for signal in signals):
        return TrainingStatus.reduce_load
    if strong and (len(strong) >= 2 or moderate_dimensions - {strong[0].dimension}):
        return TrainingStatus.reduce_load
    if len(moderate_dimensions) >= 3:
        return TrainingStatus.reduce_load
    if has_pain_moderate or len(moderate_dimensions) >= 2 or strong:
        return TrainingStatus.watch
    return TrainingStatus.normal


def _group(signals: list[ReadinessSignal], dimension: str) -> list[dict[str, Any]]:
    return [signal.model_dump(mode="json") for signal in signals if signal.dimension == dimension]


def _source_snapshot(summary, checkins: list[DailyRecoveryCheckin], signals: list[ReadinessSignal]) -> dict[str, Any]:
    return {
        "summary": summary.model_dump(mode="json"),
        "recovery_checkins": [
            {
                "checkin_date": item.checkin_date.isoformat(),
                "sleep_quality": item.sleep_quality,
                "subjective_fatigue": item.subjective_fatigue,
                "muscle_soreness": item.muscle_soreness,
                "stress_level": item.stress_level,
                "mood_level": item.mood_level,
                "leg_feeling": item.leg_feeling,
                "resting_heart_rate_bpm": item.resting_heart_rate_bpm,
                "hrv_value": float(item.hrv_value) if item.hrv_value is not None else None,
                "hrv_metric": item.hrv_metric,
                "hrv_source": item.hrv_source,
                "pain_level": item.pain_level,
                "pain_trend": item.pain_trend.value,
                "pain_affects_gait": item.pain_affects_gait,
                "has_illness_symptoms": bool(item.illness_symptoms),
            }
            for item in checkins
        ],
        "signals": [signal.model_dump(mode="json") for signal in signals],
    }


def evaluate_and_save_readiness(
    db: Session, user_id: int, assessment_date: date | None = None
) -> TrainingReadinessAssessment:
    target_date = assessment_date or local_today()
    if target_date > local_today():
        raise BadRequestError("Assessment date cannot be in the future.")
    summary = build_training_load_summary(db, user_id, target_date)
    checkins = _recent_checkins(db, user_id, target_date)
    rows = _recent_logs(db, user_id, target_date)
    external, internal = _load_signals(summary)
    internal_extra, performance = _performance_and_internal_signals(rows)
    recovery = _recovery_signals(checkins)
    pain = _pain_signals(checkins, rows)
    signals = external + internal + internal_extra + recovery + performance + pain
    data_quality = _data_quality(summary)
    status = _decide_status(data_quality, signals, summary)
    has_pain_signal = bool(pain)
    recommendations = build_recommendations(status, has_pain_signal=has_pain_signal)
    reasons = [signal.message for signal in signals if signal.level in {"moderate", "strong"}]
    if status == TrainingStatus.insufficient_data and not reasons:
        reasons = ["当前训练日志或恢复打卡不足，无法建立稳定的个人趋势。"]
    elif status == TrainingStatus.normal:
        reasons = ["现有记录未显示需要明显降负荷的组合信号。"]
    elif not reasons:
        reasons = ["出现需要关注的训练或恢复信号。"]
    if summary.missing_data:
        reasons.append("部分指标缺失，当前判断仅基于已有记录。")
    assessment = TrainingReadinessAssessment(
        user_id=user_id,
        assessment_date=target_date,
        status=status,
        data_quality=data_quality,
        metrics_json=summary.model_dump(mode="json"),
        external_load_signals_json=_group(signals, "external_load"),
        internal_load_signals_json=_group(signals, "internal_load"),
        recovery_signals_json=_group(signals, "recovery"),
        performance_signals_json=_group(signals, "performance"),
        pain_signals_json=_group(signals, "pain"),
        reasons_json=reasons,
        recommendations_json=[item.model_dump(mode="json") for item in recommendations],
        missing_data_json=summary.missing_data,
        source_snapshot_json=_source_snapshot(summary, checkins, signals),
        algorithm_version=thresholds.ALGORITHM_VERSION,
        threshold_version=thresholds.THRESHOLD_VERSION,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def get_latest_assessment(db: Session, user_id: int, assessment_date: date) -> TrainingReadinessAssessment | None:
    return db.scalar(
        select(TrainingReadinessAssessment)
        .where(
            TrainingReadinessAssessment.user_id == user_id,
            TrainingReadinessAssessment.assessment_date == assessment_date,
        )
        .order_by(TrainingReadinessAssessment.created_at.desc(), TrainingReadinessAssessment.id.desc())
        .limit(1)
    )


def get_or_create_today_assessment(db: Session, user_id: int) -> TrainingReadinessAssessment:
    today = local_today()
    return get_latest_assessment(db, user_id, today) or evaluate_and_save_readiness(db, user_id, today)


def get_assessment_by_date(db: Session, user_id: int, assessment_date: date) -> TrainingReadinessAssessment:
    assessment = get_latest_assessment(db, user_id, assessment_date)
    if assessment is None:
        raise NotFoundError("Training readiness assessment not found.")
    return assessment


def list_assessments(db: Session, user_id: int, days: int) -> list[TrainingReadinessAssessment]:
    if days < 1 or days > 120:
        raise BadRequestError("days must be between 1 and 120.")
    start = local_today() - timedelta(days=days - 1)
    return list(
        db.scalars(
            select(TrainingReadinessAssessment)
            .where(
                TrainingReadinessAssessment.user_id == user_id,
                TrainingReadinessAssessment.assessment_date >= start,
            )
            .order_by(TrainingReadinessAssessment.assessment_date.desc(), TrainingReadinessAssessment.created_at.desc())
        )
    )
