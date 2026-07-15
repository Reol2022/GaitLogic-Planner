from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import PlannedWorkout
from server.services.training_facts.common import base_facts, decimal_float, enum_value, is_high_intensity
from server.services.weekly_review_stats_service import build_weekly_review_metrics


def build_weekly_facts(
    db: Session,
    user_id: int,
    cycle_id: int,
    source_block_id: int,
    target_block_id: int | None = None,
) -> dict:
    metrics = build_weekly_review_metrics(db, user_id, cycle_id, source_block_id)
    next_workouts = []
    if target_block_id is not None:
        next_workouts = list(
            db.scalars(
                select(PlannedWorkout)
                .where(PlannedWorkout.user_id == user_id, PlannedWorkout.block_id == target_block_id)
                .order_by(PlannedWorkout.workout_date, PlannedWorkout.session_index, PlannedWorkout.id)
            )
        )
    facts = base_facts()
    facts["weekly"] = {
        "week_start_date": metrics.week_start_date.isoformat(),
        "week_end_date": metrics.week_end_date.isoformat(),
        "planned_distance_km": metrics.planned_distance_km,
        "actual_distance_km": metrics.actual_distance_km,
        "completion_rate": metrics.completion_rate,
        "planned_training_days": metrics.planned_workout_days,
        "actual_training_days": metrics.completed_workout_days,
        "key_workout_planned_count": len(metrics.key_workouts),
        "key_workout_completed_count": sum(1 for item in metrics.key_workouts if item.get("status", "").startswith("completed")),
        "long_run": metrics.long_run,
        "high_intensity_count": metrics.completed_high_count,
        "srpe_load_au": metrics.rolling_7d_srpe_load_au,
        "recent_7d_distance_km": metrics.recent_7d_distance_km,
        "baseline_28d_weekly_distance_km": metrics.recent_28d_weekly_avg_km,
        "recovery_checkin_coverage_ratio": metrics.recovery_checkin_coverage_ratio,
        "avg_sleep_hours": metrics.avg_sleep_hours,
        "max_pain_level": metrics.max_pain_level,
        "training_alert": any(item.get("alert_message") for item in metrics.daily_workouts),
        "consecutive_high_intensity_days": metrics.consecutive_high_intensity_days,
        "missing_data": metrics.missing_fields,
        "low_completion": metrics.completion_rate < 0.75,
        "high_completion": metrics.completion_rate >= 0.9 and metrics.valid_log_count > 0,
        "multiple_missed_key_sessions": sum(1 for item in metrics.key_workouts if not str(item.get("status", "")).startswith("completed")) >= 2,
        "high_load_recovery_notice": bool(metrics.recent_to_baseline_load_ratio is not None and metrics.recent_to_baseline_load_ratio >= 1.25),
        "pain_reported": bool(metrics.max_pain_level is not None and metrics.max_pain_level >= 1),
        "recovery_data_incomplete": bool(metrics.missing_fields),
    }
    next_distance = sum(decimal_float(item.planned_distance_km) or 0 for item in next_workouts)
    current_distance = metrics.planned_distance_km or 0
    facts["plan"] = {
        "next_week": {
            "target_block_id": target_block_id,
            "planned_distance_km": round(next_distance, 2),
            "volume_change_ratio": None if current_distance <= 0 else round((next_distance - current_distance) / current_distance, 4),
            "key_workout_count": sum(1 for item in next_workouts if is_high_intensity(enum_value(item.main_type_normalized))),
            "volume_increase_notice": bool(current_distance > 0 and (next_distance - current_distance) / current_distance >= 0.15),
            "too_many_key_sessions": sum(1 for item in next_workouts if is_high_intensity(enum_value(item.main_type_normalized))) >= 3,
            "missing_rest_day": sum(1 for item in next_workouts if enum_value(item.main_type_normalized) == "rest") == 0 and bool(next_workouts),
            "workouts": [
                {
                    "id": item.id,
                    "date": item.workout_date.isoformat() if item.workout_date else None,
                    "distance_km": decimal_float(item.planned_distance_km) or 0,
                    "main_type": enum_value(item.main_type_normalized),
                    "plan_version": item.plan_version,
                }
                for item in next_workouts
            ],
        }
    }
    facts["system"]["context_type"] = "weekly_review"
    facts["system"]["cycle_id"] = cycle_id
    facts["system"]["source_block_id"] = source_block_id
    facts["system"]["target_block_id"] = target_block_id
    return facts
