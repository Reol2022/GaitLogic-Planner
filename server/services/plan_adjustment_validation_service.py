from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PlanAdjustmentDraft, PlanAdjustmentItem, PlannedWorkout
from planner_core.enums import (
    PlanAdjustmentAction,
    PlanAdjustmentDraftStatus,
    TrainingStatus,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)
from server.common.exceptions import BadRequestError, NotFoundError
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES
from server.schemas.weekly_review import WeeklyReviewAIOutput
from server.services.weekly_review_stats_service import COMPLETED_STATUSES, local_today

MAX_WEEKLY_INCREASE_RATIO = 1.15
INTENSITY_RANK = {
    WorkoutMainTypeNormalized.rest.value: 0,
    WorkoutMainTypeNormalized.recovery.value: 1,
    WorkoutMainTypeNormalized.easy.value: 2,
    WorkoutMainTypeNormalized.easy_with_speed.value: 3,
    WorkoutMainTypeNormalized.long_run.value: 3,
    WorkoutMainTypeNormalized.mixed.value: 4,
    WorkoutMainTypeNormalized.tempo.value: 5,
    WorkoutMainTypeNormalized.interval_speed.value: 6,
    WorkoutMainTypeNormalized.unknown.value: 3,
}


def get_adjustment_draft(db: Session, draft_id: int, user_id: int, *, lock: bool = False) -> PlanAdjustmentDraft:
    stmt = (
        select(PlanAdjustmentDraft)
        .options(
            selectinload(PlanAdjustmentDraft.items).selectinload(PlanAdjustmentItem.planned_workout),
            selectinload(PlanAdjustmentDraft.review_report),
        )
        .where(PlanAdjustmentDraft.id == draft_id, PlanAdjustmentDraft.user_id == user_id)
    )
    if lock:
        stmt = stmt.with_for_update()
    draft = db.scalar(stmt)
    if draft is None:
        raise NotFoundError("Adjustment draft not found.")
    draft.items.sort(key=lambda item: (item.planned_workout.workout_date or date.max, item.id))
    return draft


def _assert_workout_can_change(workout: PlannedWorkout, user_id: int, target_block_id: int) -> None:
    if workout.user_id != user_id or workout.block_id != target_block_id:
        raise BadRequestError("Adjustment item does not belong to the current user's target block.")
    if workout.workout_date and workout.workout_date < local_today():
        raise BadRequestError("Historical workouts cannot be adjusted.")
    if workout.workout_log and workout.workout_log.status_normalized in COMPLETED_STATUSES:
        raise BadRequestError("Completed workouts cannot be adjusted.")


def _validate_values(
    action: PlanAdjustmentAction,
    original_distance: float,
    suggested_distance: float,
    original_type: str,
    suggested_type: str,
    training_status: TrainingStatus,
    max_pain_level: int | None,
) -> None:
    if suggested_distance < 0:
        raise BadRequestError("Suggested distance cannot be negative.")
    if action == PlanAdjustmentAction.reduce and suggested_distance > original_distance:
        raise BadRequestError("A reduce adjustment cannot increase distance.")
    if action == PlanAdjustmentAction.rest and suggested_distance != 0:
        raise BadRequestError("A rest adjustment must have zero distance.")
    if action == PlanAdjustmentAction.rest and suggested_type != WorkoutMainTypeNormalized.rest.value:
        raise BadRequestError("A rest adjustment must use the rest workout type.")
    if action == PlanAdjustmentAction.keep and (
        suggested_distance != original_distance or suggested_type != original_type
    ):
        raise BadRequestError("A keep adjustment must preserve distance and workout type.")
    if training_status == TrainingStatus.reduce_load and suggested_distance > original_distance:
        raise BadRequestError("Reduce-load status cannot increase workout distance.")
    if max_pain_level is not None and max_pain_level >= 3:
        if INTENSITY_RANK.get(suggested_type, 99) > INTENSITY_RANK.get(original_type, 99):
            raise BadRequestError("Workout intensity cannot increase when notable pain is recorded.")


def _validate_resulting_week(
    workouts: list[PlannedWorkout], suggestions: dict[int, tuple[str, float]], original_total: float,
    training_status: TrainingStatus,
) -> None:
    resulting: list[tuple[date, str, float]] = []
    for workout in workouts:
        workout_type = workout.main_type_normalized.value
        distance = float(workout.planned_distance_km or 0)
        if workout.id in suggestions:
            workout_type, distance = suggestions[workout.id]
        if workout.workout_date:
            resulting.append((workout.workout_date, workout_type, distance))
    resulting.sort(key=lambda item: item[0])
    high_dates = [item[0] for item in resulting if item[1] in HIGH_INTENSITY_TYPES]
    if any(right - left == timedelta(days=1) for left, right in zip(high_dates, high_dates[1:])):
        raise BadRequestError("Adjustments cannot produce consecutive high-intensity days.")
    suggested_total = sum(item[2] for item in resulting)
    if training_status == TrainingStatus.reduce_load and suggested_total > original_total:
        raise BadRequestError("Reduce-load status cannot increase next week's total distance.")
    if original_total > 0 and suggested_total > original_total * MAX_WEEKLY_INCREASE_RATIO:
        raise BadRequestError("Suggested weekly distance increases beyond the community safety limit.")


def validate_ai_adjustments(
    db: Session,
    user_id: int,
    target_block_id: int,
    output: WeeklyReviewAIOutput,
    training_status: TrainingStatus,
    max_pain_level: int | None,
) -> list[PlannedWorkout]:
    if output.training_status != training_status:
        raise BadRequestError("AI training_status must match the deterministic rule result.")
    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(PlannedWorkout.user_id == user_id, PlannedWorkout.block_id == target_block_id)
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order)
        )
    )
    by_id = {item.id: item for item in workouts}
    suggestions: dict[int, tuple[str, float]] = {}
    for adjustment in output.adjustments:
        workout = by_id.get(adjustment.planned_workout_id)
        if workout is None:
            raise BadRequestError("AI returned a workout outside the target block.")
        _assert_workout_can_change(workout, user_id, target_block_id)
        original_distance = float(workout.planned_distance_km or 0)
        original_type = workout.main_type_normalized.value
        suggested_type = adjustment.suggested_main_type.value
        _validate_values(
            adjustment.action,
            original_distance,
            adjustment.suggested_distance_km,
            original_type,
            suggested_type,
            training_status,
            max_pain_level,
        )
        suggestions[workout.id] = (suggested_type, adjustment.suggested_distance_km)
    _validate_resulting_week(
        workouts,
        suggestions,
        sum(float(item.planned_distance_km or 0) for item in workouts),
        training_status,
    )
    return workouts


def validate_draft_items(
    db: Session, draft: PlanAdjustmentDraft, selected_item_ids: set[int]
) -> list[PlanAdjustmentItem]:
    if draft.status in {PlanAdjustmentDraftStatus.applied, PlanAdjustmentDraftStatus.rejected, PlanAdjustmentDraftStatus.invalid}:
        raise BadRequestError("This adjustment draft can no longer be applied.")
    selected = [item for item in draft.items if item.id in selected_item_ids]
    if len(selected) != len(selected_item_ids):
        raise BadRequestError("Selected items must belong to the adjustment draft.")
    if any(item.is_applied for item in selected):
        raise BadRequestError("An applied adjustment item cannot be applied again.")

    report = draft.review_report
    training_status = report.training_status
    max_pain = (report.metrics_json or {}).get("max_pain_level")
    workouts = list(
        db.scalars(
            select(PlannedWorkout)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(
                PlannedWorkout.user_id == draft.user_id,
                PlannedWorkout.block_id == draft.target_block_id,
            )
            .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order)
        )
    )
    suggestions: dict[int, tuple[str, float]] = {}
    for item in selected:
        workout = item.planned_workout
        _assert_workout_can_change(workout, draft.user_id, draft.target_block_id)
        original_type = item.original_main_type or workout.main_type_normalized.value
        suggested_type = item.suggested_main_type or original_type
        original_distance = float(item.original_distance_km or 0)
        suggested_distance = float(item.suggested_distance_km or 0)
        _validate_values(
            item.action, original_distance, suggested_distance, original_type, suggested_type, training_status, max_pain
        )
        suggestions[workout.id] = (suggested_type, suggested_distance)
    _validate_resulting_week(
        workouts,
        suggestions,
        float(draft.original_week_distance_km or 0),
        training_status,
    )
    return selected
