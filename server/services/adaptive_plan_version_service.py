from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AdaptivePlanVersionRecord, PlannedWorkout
from planner_core.enums import WorkoutMainTypeNormalized
from server.common.exceptions import BadRequestError, NotFoundError


class AdaptivePlanVersionService:
    @staticmethod
    def list_versions(db: Session, *, user_id: int) -> list[AdaptivePlanVersionRecord]:
        return list(
            db.scalars(
                select(AdaptivePlanVersionRecord)
                .where(AdaptivePlanVersionRecord.user_id == user_id)
                .order_by(AdaptivePlanVersionRecord.version_number.desc())
            )
        )

    def rollback(
        self,
        db: Session,
        *,
        user_id: int,
        version_id: int,
        reason: str,
    ) -> AdaptivePlanVersionRecord:
        try:
            target = db.scalar(
                select(AdaptivePlanVersionRecord).where(
                    AdaptivePlanVersionRecord.id == version_id,
                    AdaptivePlanVersionRecord.user_id == user_id,
                )
            )
            if target is None:
                raise NotFoundError("Plan version not found.")
            plan_ids = [item["plan_id"] for item in target.before_snapshot_json]
            workouts = list(
                db.scalars(
                    select(PlannedWorkout)
                    .where(PlannedWorkout.id.in_(plan_ids), PlannedWorkout.user_id == user_id)
                    .with_for_update()
                )
            )
            by_id = {item.id: item for item in workouts}
            if len(by_id) != len(plan_ids):
                raise BadRequestError("Rollback target is no longer complete.")
            current = [
                {
                    "plan_id": item.id,
                    "plan_version": item.plan_version,
                    "content": item.planned_content,
                    "distance_km": float(item.planned_distance_km) if item.planned_distance_km is not None else None,
                    "main_type": item.main_type_normalized.value,
                    "target_pace_text": item.target_pace_text,
                }
                for item in workouts
            ]
            restored: list[dict] = []
            for snapshot in target.before_snapshot_json:
                workout = by_id[snapshot["plan_id"]]
                workout.planned_content = snapshot["content"]
                workout.planned_distance_km = Decimal(str(snapshot["distance_km"])) if snapshot["distance_km"] is not None else None
                workout.main_type_normalized = WorkoutMainTypeNormalized(snapshot["main_type"])
                workout.main_type_raw = snapshot["main_type"]
                workout.target_pace_text = snapshot.get("target_pace_text")
                workout.plan_version += 1
                restored.append({**snapshot, "plan_version": workout.plan_version})
            latest = db.scalar(
                select(AdaptivePlanVersionRecord)
                .where(AdaptivePlanVersionRecord.user_id == user_id)
                .order_by(AdaptivePlanVersionRecord.version_number.desc())
                .limit(1)
                .with_for_update()
            )
            record = AdaptivePlanVersionRecord(
                user_id=user_id,
                proposal_id=None,
                version_number=(latest.version_number + 1 if latest else 1),
                previous_version_id=latest.id if latest else None,
                rollback_of_version_id=target.id,
                reason=reason,
                actor_user_id=user_id,
                source="controlled_rollback",
                before_snapshot_json=current,
                after_snapshot_json=restored,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        except Exception:
            db.rollback()
            raise
