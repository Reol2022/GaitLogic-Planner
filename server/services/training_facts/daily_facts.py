from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin, PlannedWorkout, WorkoutLog
from server.domain.decision_readiness import DecisionReadiness
from server.services.training_facts.common import base_facts, date_text, decimal_float, enum_value, is_high_intensity, workout_type_bucket
from server.services.training_load_service import build_training_load_summary


def build_daily_facts(db: Session, user_id: int, target_date: date) -> dict[str, Any]:
    facts = base_facts()
    workout = db.scalar(
        select(PlannedWorkout)
        .where(PlannedWorkout.user_id == user_id, PlannedWorkout.workout_date == target_date)
        .order_by(PlannedWorkout.session_index, PlannedWorkout.id)
    )
    if workout is None:
        facts["planned_workout"] = {"exists": False}
    else:
        main_type = enum_value(workout.main_type_normalized) or workout.main_type_raw or "unknown"
        facts["planned_workout"] = {
            "exists": True,
            "id": workout.id,
            "date": date_text(workout.workout_date),
            "type": "rest" if main_type == "rest" else main_type,
            "intensity_level": _intensity_level(main_type),
            "high_intensity": is_high_intensity(main_type),
            "distance_km": decimal_float(workout.planned_distance_km),
            "content": workout.planned_content,
            "plan_version": workout.plan_version,
        }
    previous_log = db.scalar(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == user_id, WorkoutLog.activity_date == target_date - timedelta(days=1))
        .order_by(WorkoutLog.id.desc())
    )
    facts["previous_day"] = {
        "high_intensity": bool(previous_log and _log_high_intensity(previous_log)),
        "duration_seconds": previous_log.actual_duration_seconds if previous_log else None,
        "workout_type": previous_log.workout_type if previous_log else None,
    }
    checkin = db.scalar(
        select(DailyRecoveryCheckin).where(
            DailyRecoveryCheckin.user_id == user_id,
            DailyRecoveryCheckin.checkin_date == target_date,
        )
    )
    facts["recovery"] = _recovery_facts(checkin)
    try:
        load = build_training_load_summary(db, user_id, target_date)
        facts["recent_training"] = {
            "rolling_7d_distance_km": load.rolling_7d_distance_km,
            "rolling_7d_srpe_load_au": load.rolling_7d_srpe_load_au,
            "baseline_28d_weekly_distance_km": load.baseline_28d_weekly_distance_km,
            "recent_to_baseline_load_ratio": load.recent_to_baseline_load_ratio,
            "load_change_percentage": load.load_change_percentage,
            # Preserve individual missing reasons.  RPE and recovery coverage
            # constrain their own analyses but are not automatically a global
            # TODAY decision blocker.
            "missing_data": list(load.missing_data),
        }
    except Exception:
        facts["recent_training"] = {"core_data_unavailable": True}
    facts["system"]["context_type"] = "daily_adjustment"
    facts["system"]["target_date"] = target_date.isoformat()
    facts["system"]["data_limited"] = _data_limited(facts)
    facts["system"]["decision_readiness"] = _decision_readiness(facts).value
    facts["system"]["data_limitations"] = _data_limitations(facts)
    facts["system"]["training_alert"] = bool(facts["recovery"].get("training_alert"))
    recovery = facts["recovery"]
    recent = facts["recent_training"]
    facts["system"]["poor_leg_feel_with_intensity"] = bool(
        facts["planned_workout"].get("high_intensity") and recovery.get("leg_feel") is not None and recovery.get("leg_feel") <= 2
    )
    facts["system"]["high_fatigue_with_intensity"] = bool(
        facts["planned_workout"].get("high_intensity")
        and recovery.get("subjective_fatigue") is not None
        and recovery.get("subjective_fatigue") >= 4
    )
    load_ratio = recent.get("recent_to_baseline_load_ratio")
    if load_ratio is not None:
        facts["system"]["recent_high_load"] = bool(load_ratio >= 1.25)
    return facts


def _intensity_level(main_type: str) -> str:
    bucket = workout_type_bucket(main_type)
    if bucket == "key":
        if main_type in {"tempo", "threshold", "t1", "t2"}:
            return "threshold"
        if main_type in {"interval_speed", "interval", "i"}:
            return "interval"
        return "repetition"
    if bucket == "rest":
        return "rest"
    return "easy"


def _log_high_intensity(log: WorkoutLog) -> bool:
    if log.status_normalized.value == "completed_high":
        return True
    return is_high_intensity(log.workout_type)


def _recovery_facts(checkin: DailyRecoveryCheckin | None) -> dict[str, Any]:
    if checkin is None:
        return {}
    return {
        "sleep_hours": round(checkin.sleep_duration_minutes / 60, 2) if checkin.sleep_duration_minutes else None,
        "sleep_quality": checkin.sleep_quality,
        "leg_feel": checkin.leg_feeling,
        "subjective_fatigue": checkin.subjective_fatigue,
        "hrv": decimal_float(checkin.hrv_value),
        "morning_heart_rate": checkin.resting_heart_rate_bpm,
        "pain_level": checkin.pain_level,
        "pain_location": checkin.pain_location,
        "training_alert": bool(checkin.illness_symptoms or checkin.pain_affects_gait),
    }


def _data_limited(facts: dict[str, Any]) -> bool:
    """Return whether deterministic TODAY core facts are unavailable.

    Recovery fields are intentionally excluded: missing sleep, leg feel, or
    subjective fatigue limits recovery-specific conclusions, but historical
    load and the planned workout can still support a constrained TODAY result.
    """
    recent = facts.get("recent_training") or {}
    if recent.get("core_data_unavailable"):
        return True
    return "training_logs" in set(recent.get("missing_data") or [])


def _data_limitations(facts: dict[str, Any]) -> list[str]:
    recent = facts.get("recent_training") or {}
    return sorted({str(item) for item in recent.get("missing_data") or []})


def _decision_readiness(facts: dict[str, Any]) -> DecisionReadiness:
    if _data_limited(facts):
        return DecisionReadiness.BLOCKED
    if _data_limitations(facts):
        return DecisionReadiness.PARTIAL
    return DecisionReadiness.READY
