from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import ExternalActivity, PlannedWorkout, WorkoutLog, WorkoutLogExternalActivity
from planner_core.enums import PainScaleVersion
from server.common.exceptions import NotFoundError
from server.schemas.workout_log import WorkoutCompletionContextRead, WorkoutLogUpdate
from server.services.planned_workout_service import get_planned_workout


def get_workout_log_by_planned_workout(
    db: Session,
    planned_workout_id: int,
    user_id: int,
) -> WorkoutLog:
    get_planned_workout(db, planned_workout_id, user_id)
    log = db.scalar(
        select(WorkoutLog).where(
            WorkoutLog.planned_workout_id == planned_workout_id,
            WorkoutLog.user_id == user_id,
        )
    )
    if log is None:
        raise NotFoundError("Workout log not found.")
    return log


def update_workout_log(
    db: Session,
    planned_workout_id: int,
    payload: WorkoutLogUpdate,
    user_id: int,
) -> WorkoutLog:
    log = get_workout_log_by_planned_workout(db, planned_workout_id, user_id)
    data = payload.model_dump(exclude_unset=True)
    actual_distance = data.get("actual_distance_km", log.actual_distance_km)
    actual_duration = data.get("actual_duration_seconds", log.actual_duration_seconds)
    should_auto_calculate_pace = (
        "avg_pace_seconds_per_km" not in data or data.get("avg_pace_seconds_per_km") in (None, 0)
    )
    if (
        should_auto_calculate_pace
        and actual_distance is not None
        and actual_duration is not None
        and actual_distance > 0
    ):
        data["avg_pace_seconds_per_km"] = int(round(actual_duration / float(actual_distance)))
    if "pain_level" in data and "pain_scale_version" not in data:
        data["pain_scale_version"] = PainScaleVersion.native_0_10
    for key, value in data.items():
        setattr(log, key, value)
    log.subjective_status = _subjective_status(log)
    db.commit()
    db.refresh(log)
    return log


def get_completion_context(db: Session, planned_workout_id: int, user_id: int) -> WorkoutCompletionContextRead:
    workout = get_planned_workout(db, planned_workout_id, user_id)
    log = db.scalar(
        select(WorkoutLog).where(
            WorkoutLog.planned_workout_id == planned_workout_id,
            WorkoutLog.user_id == user_id,
        )
    )
    linked = []
    if log is not None:
        linked = list(
            db.scalars(
                select(ExternalActivity)
                .join(WorkoutLogExternalActivity, WorkoutLogExternalActivity.external_activity_id == ExternalActivity.id)
                .where(WorkoutLogExternalActivity.workout_log_id == log.id)
                .order_by(ExternalActivity.start_time_local)
            )
        )
    candidates = []
    if workout.workout_date is not None:
        candidates = list(
            db.scalars(
                select(ExternalActivity).where(
                    ExternalActivity.user_id == user_id,
                    ExternalActivity.activity_date == workout.workout_date,
                    ExternalActivity.workout_log_id.is_(None),
                    ExternalActivity.resolution_status.in_(["pending", "needs_review"]),
                    ExternalActivity.processing_status != "ignored",
                )
            )
        )
    objective = {}
    if log is not None:
        objective = {
            key: getattr(log, key)
            for key in [
                "actual_distance_km",
                "actual_duration_seconds",
                "moving_time_seconds",
                "elapsed_time_seconds",
                "avg_pace_seconds_per_km",
                "avg_heart_rate",
                "max_heart_rate",
                "average_cadence_spm",
                "max_cadence_spm",
                "elevation_gain_m",
                "calories_kcal",
            ]
            if getattr(log, key) is not None
        }
    missing = []
    if log is not None:
        for key in ["rpe", "pain_level", "leg_feeling", "review_note"]:
            if getattr(log, key) in (None, ""):
                missing.append(key)
    mode = "manual_full"
    if log is not None and linked:
        mode = "garmin_prefilled" if missing else "already_completed"
    elif log is not None:
        mode = "already_completed"
    elif candidates:
        mode = "garmin_prefilled"
    return WorkoutCompletionContextRead(
        existing_workout_log=log,
        linked_garmin_activities=linked,
        candidate_garmin_activities=candidates,
        prefilled_objective_fields=objective,
        subjective_fields_missing=missing,
        field_conflicts=[],
        mode=mode,
    )


def _subjective_status(log: WorkoutLog) -> str:
    required = [log.rpe, log.pain_level, log.leg_feeling, log.review_note]
    return "completed" if all(value not in (None, "") for value in required) else "pending"
