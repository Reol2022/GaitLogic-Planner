from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from planner_core.enums import PlanAdjustmentAction, PlanAdjustmentDraftStatus, WorkoutMainTypeNormalized
from server.common.exceptions import BadRequestError
from server.schemas.weekly_review import PlanAdjustmentApplyResponse, PlanAdjustmentItemUpdate
from server.services.plan_adjustment_validation_service import get_adjustment_draft, validate_draft_items


def update_adjustment_item(
    db: Session,
    user_id: int,
    draft_id: int,
    item_id: int,
    payload: PlanAdjustmentItemUpdate,
):
    draft = get_adjustment_draft(db, draft_id, user_id)
    if draft.status not in {PlanAdjustmentDraftStatus.draft, PlanAdjustmentDraftStatus.partially_applied}:
        raise BadRequestError("This adjustment draft can no longer be edited.")
    item = next((candidate for candidate in draft.items if candidate.id == item_id), None)
    if item is None:
        raise BadRequestError("Adjustment item does not belong to the draft.")
    if item.is_applied:
        raise BadRequestError("An applied adjustment item cannot be edited.")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "suggested_distance_km" and value is not None:
            value = Decimal(str(value))
        if key == "suggested_main_type" and value is not None:
            value = value.value
        setattr(item, key, value)
    try:
        selected_ids = {candidate.id for candidate in draft.items if candidate.is_selected}
        if item.is_selected:
            selected_ids.add(item.id)
        validate_draft_items(db, draft, selected_ids)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


def apply_adjustment_draft(
    db: Session, user_id: int, draft_id: int, selected_item_ids: list[int]
) -> PlanAdjustmentApplyResponse:
    try:
        draft = get_adjustment_draft(db, draft_id, user_id, lock=True)
        selected_ids = set(selected_item_ids) or {
            item.id for item in draft.items if item.is_selected and not item.is_applied
        }
        if not selected_ids:
            raise BadRequestError("Select at least one adjustment item before applying.")
        selected = validate_draft_items(db, draft, selected_ids)
        now = datetime.utcnow()
        before: list[dict] = []
        after: list[dict] = []
        applied_ids: list[int] = []
        for item in selected:
            workout = item.planned_workout
            item.is_selected = True
            before.append(
                {
                    "planned_workout_id": workout.id,
                    "content": workout.planned_content,
                    "distance_km": float(workout.planned_distance_km or 0),
                    "main_type": workout.main_type_normalized.value,
                    "target_pace_text": workout.target_pace_text,
                }
            )
            if item.action != PlanAdjustmentAction.keep:
                workout.planned_content = item.suggested_content
                workout.planned_distance_km = Decimal(str(item.suggested_distance_km or 0))
                workout.main_type_normalized = WorkoutMainTypeNormalized(
                    item.suggested_main_type or item.original_main_type or "unknown"
                )
                workout.main_type_raw = workout.main_type_normalized.value
                workout.target_pace_text = item.suggested_target_pace_text
            item.is_applied = True
            item.applied_at = now
            applied_ids.append(item.id)
            after.append(
                {
                    "planned_workout_id": workout.id,
                    "content": workout.planned_content,
                    "distance_km": float(workout.planned_distance_km or 0),
                    "main_type": workout.main_type_normalized.value,
                    "target_pace_text": workout.target_pace_text,
                }
            )

        remaining = [item for item in draft.items if not item.is_applied and item.action != PlanAdjustmentAction.keep]
        draft.status = (
            PlanAdjustmentDraftStatus.partially_applied if remaining else PlanAdjustmentDraftStatus.applied
        )
        draft.applied_at = now
        db.commit()
        return PlanAdjustmentApplyResponse(
            draft_id=draft.id,
            status=draft.status,
            applied_item_ids=applied_ids,
            before=before,
            after=after,
        )
    except Exception:
        db.rollback()
        raise


def reject_adjustment_draft(db: Session, user_id: int, draft_id: int):
    draft = get_adjustment_draft(db, draft_id, user_id)
    if draft.status in {PlanAdjustmentDraftStatus.applied, PlanAdjustmentDraftStatus.rejected}:
        raise BadRequestError("This adjustment draft can no longer be rejected.")
    draft.status = PlanAdjustmentDraftStatus.rejected
    draft.rejected_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    return draft
