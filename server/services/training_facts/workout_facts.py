from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlannedWorkout, WorkoutLog
from server.common.exceptions import NotFoundError
from server.services.training_facts.common import base_facts, date_text, decimal_float, enum_value, is_high_intensity


def build_workout_facts(db: Session, user_id: int, workout_log_id: int) -> dict:
    log = db.scalar(
        select(WorkoutLog)
        .options(selectinload(WorkoutLog.planned_workout))
        .where(WorkoutLog.id == workout_log_id, WorkoutLog.user_id == user_id)
    )
    if log is None:
        raise NotFoundError("Workout log not found.")
    planned: PlannedWorkout | None = log.planned_workout
    facts = base_facts()
    planned_type = enum_value(planned.main_type_normalized) if planned else None
    facts["planned_workout"] = {
        "exists": planned is not None,
        "id": planned.id if planned else None,
        "type": planned_type,
        "distance_km": decimal_float(planned.planned_distance_km) if planned else None,
        "content": planned.planned_content if planned else None,
        "high_intensity": is_high_intensity(planned_type),
        "plan_version": planned.plan_version if planned else None,
    }
    actual_distance = decimal_float(log.actual_distance_km)
    planned_distance = decimal_float(planned.planned_distance_km) if planned else None
    facts["workout"] = {
        "log_id": log.id,
        "activity_date": date_text(log.activity_date),
        "status": enum_value(log.status_normalized),
        "type": log.workout_type or planned_type,
        "distance_km": actual_distance,
        "duration_seconds": log.actual_duration_seconds,
        "avg_pace_seconds_per_km": log.avg_pace_seconds_per_km,
        "avg_heart_rate": log.avg_heart_rate,
        "rpe": log.rpe,
        "review_note": log.review_note,
        "pain_level": log.pain_level,
        "pain_location": log.pain_location,
        "alert_message": log.alert_message,
        "distance_delta_ratio": _delta_ratio(actual_distance, planned_distance),
        "completed": enum_value(log.status_normalized) in {"completed_high", "completed_normal", "completed_adjusted"},
        "subjective_feedback_missing": any(getattr(log, key) in (None, "") for key in ["rpe", "pain_level", "leg_feeling", "review_note"]),
    }
    facts["workout"]["completed_as_planned"] = bool(
        facts["workout"]["completed"]
        and facts["workout"]["distance_delta_ratio"] is not None
        and abs(facts["workout"]["distance_delta_ratio"]) <= 0.1
        and enum_value(log.status_normalized) == "completed_normal"
    )
    facts["workout"]["distance_over_plan"] = bool(
        facts["workout"]["distance_delta_ratio"] is not None and facts["workout"]["distance_delta_ratio"] >= 0.2
    )
    facts["workout"]["distance_under_plan"] = bool(
        facts["workout"]["distance_delta_ratio"] is not None and facts["workout"]["distance_delta_ratio"] <= -0.2
    )
    facts["workout"]["easy_rpe_high"] = bool(
        planned_type in {"easy", "recovery", "easy_with_speed"} and log.rpe is not None and log.rpe >= 7
    )
    facts["workout"]["pain_reported"] = bool(log.pain_level is not None and log.pain_level >= 1)
    facts["workout"]["alert_reported"] = bool(log.alert_message)
    facts["workout"]["incomplete_key_session"] = bool(
        is_high_intensity(planned_type) and enum_value(log.status_normalized) in {"missed", "skipped", "rest_or_cancelled"}
    )
    facts["system"]["context_type"] = "workout_review"
    facts["system"]["source_updated_at"] = log.updated_at.isoformat() if log.updated_at else None
    return facts


def _delta_ratio(actual: float | None, planned: float | None) -> float | None:
    if actual is None or planned is None or planned <= 0:
        return None
    return round((actual - planned) / planned, 4)
