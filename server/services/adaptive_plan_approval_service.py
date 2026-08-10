from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.adaptive_plan.schemas import PlanAdjustmentProposal
from planner_core.database.models import (
    AdaptivePlanVersionRecord,
    PlannedWorkout,
    TrainingAdjustmentDraft,
)
from planner_core.enums import WorkoutMainTypeNormalized, WorkoutStatusNormalized
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.adaptive_plan import AdaptiveApprovalResult


COMPLETED = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}


def _snapshot(workout: PlannedWorkout) -> dict:
    return {
        "plan_id": workout.id,
        "plan_version": workout.plan_version,
        "workout_date": workout.workout_date.isoformat() if workout.workout_date else None,
        "content": workout.planned_content,
        "distance_km": float(workout.planned_distance_km) if workout.planned_distance_km is not None else None,
        "main_type": workout.main_type_normalized.value,
        "target_pace_text": workout.target_pace_text,
    }


class AdaptivePlanApprovalService:
    def persist_proposal(
        self,
        db: Session,
        *,
        user_id: int,
        proposal: PlanAdjustmentProposal,
        cycle_id: int | None = None,
    ) -> TrainingAdjustmentDraft:
        if proposal.user_id != user_id:
            raise BadRequestError("Proposal owner does not match the authenticated user.")
        record = TrainingAdjustmentDraft(
            user_id=user_id,
            cycle_id=cycle_id,
            week_start=proposal.week_start,
            status="pending_approval",
            source_type="weekly_review_v0130",
            adjustment_json=proposal.model_dump(mode="json"),
            explanation_json={
                "reason_codes": proposal.reason_codes,
                "warnings": proposal.warnings,
                "limitations": proposal.limitations,
            },
            original_plan_snapshot_json=[
                {
                    "plan_id": item.plan_id,
                    "base_plan_version": item.base_plan_version,
                    **item.before.model_dump(mode="json"),
                }
                for item in proposal.changes
            ],
            facts_hash=None,
            source_version="adaptive-proposal-1.0.0",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def approve(self, db: Session, *, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
        try:
            record = db.scalar(
                select(TrainingAdjustmentDraft)
                .where(
                    TrainingAdjustmentDraft.id == proposal_id,
                    TrainingAdjustmentDraft.user_id == user_id,
                    TrainingAdjustmentDraft.source_type == "weekly_review_v0130",
                )
                .with_for_update()
            )
            if record is None:
                raise NotFoundError("Adaptive proposal not found.")
            if record.status == "applied":
                version = db.scalar(
                    select(AdaptivePlanVersionRecord).where(
                        AdaptivePlanVersionRecord.user_id == user_id,
                        AdaptivePlanVersionRecord.proposal_id == proposal_id,
                    )
                )
                return AdaptiveApprovalResult(
                    proposal_id=proposal_id,
                    status="applied",
                    plan_version_id=version.id if version else None,
                    applied_plan_ids=[item["plan_id"] for item in (record.applied_result_json or {}).get("after", [])],
                    duplicate=True,
                )
            if record.status != "pending_approval":
                raise BadRequestError("Only a pending proposal can be approved.")
            proposal = PlanAdjustmentProposal.model_validate(
                {**record.adjustment_json, "user_id": user_id}
            )
            ids = [item.plan_id for item in proposal.changes]
            workouts = list(
                db.scalars(
                    select(PlannedWorkout)
                    .options(selectinload(PlannedWorkout.workout_log))
                    .where(PlannedWorkout.id.in_(ids), PlannedWorkout.user_id == user_id)
                    .with_for_update()
                )
            )
            by_id = {item.id: item for item in workouts}
            if len(by_id) != len(ids):
                raise BadRequestError("Proposal contains a plan outside the authenticated user scope.")
            before: list[dict] = []
            after: list[dict] = []
            for change in proposal.changes:
                workout = by_id[change.plan_id]
                if workout.plan_version != change.base_plan_version:
                    raise BadRequestError("Plan changed after proposal generation; approval is stale.")
                if workout.is_locked or (workout.workout_log and workout.workout_log.status_normalized in COMPLETED):
                    raise BadRequestError("Locked or completed plans cannot be changed.")
                before.append(_snapshot(workout))
                workout.planned_content = change.after.content
                workout.planned_distance_km = (
                    Decimal(str(change.after.distance_km))
                    if change.after.distance_km is not None
                    else None
                )
                workout.main_type_normalized = WorkoutMainTypeNormalized(change.after.main_type)
                workout.main_type_raw = change.after.main_type
                workout.target_pace_text = change.after.target_pace_text
                workout.plan_version += 1
                after.append(_snapshot(workout))
            previous = db.scalar(
                select(AdaptivePlanVersionRecord)
                .where(AdaptivePlanVersionRecord.user_id == user_id)
                .order_by(AdaptivePlanVersionRecord.version_number.desc())
                .limit(1)
                .with_for_update()
            )
            version = AdaptivePlanVersionRecord(
                user_id=user_id,
                proposal_id=record.id,
                version_number=(previous.version_number + 1 if previous else 1),
                previous_version_id=previous.id if previous else None,
                rollback_of_version_id=None,
                reason="; ".join(proposal.reason_codes) or "User-approved adaptive proposal",
                actor_user_id=user_id,
                source="adaptive_proposal_approval",
                before_snapshot_json=before,
                after_snapshot_json=after,
            )
            db.add(version)
            db.flush()
            record.status = "applied"
            record.applied_result_json = {"version_id": version.id, "before": before, "after": after}
            db.commit()
            return AdaptiveApprovalResult(
                proposal_id=record.id,
                status="applied",
                plan_version_id=version.id,
                applied_plan_ids=ids,
            )
        except Exception:
            db.rollback()
            raise

    def reject(self, db: Session, *, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
        try:
            record = db.scalar(
                select(TrainingAdjustmentDraft)
                .where(
                    TrainingAdjustmentDraft.id == proposal_id,
                    TrainingAdjustmentDraft.user_id == user_id,
                    TrainingAdjustmentDraft.source_type == "weekly_review_v0130",
                )
                .with_for_update()
            )
            if record is None:
                raise NotFoundError("Adaptive proposal not found.")
            if record.status == "rejected":
                return AdaptiveApprovalResult(proposal_id=proposal_id, status="rejected", duplicate=True)
            if record.status != "pending_approval":
                raise BadRequestError("Only a pending proposal can be rejected.")
            record.status = "rejected"
            db.commit()
            return AdaptiveApprovalResult(proposal_id=proposal_id, status="rejected")
        except Exception:
            db.rollback()
            raise
