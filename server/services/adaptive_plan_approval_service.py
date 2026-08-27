from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.adaptive_plan.schemas import (
    PlanAdjustmentProposal,
    PlanValue,
    ProposalCandidateChange,
    TargetPlanFact,
)
from planner_core.database.models import (
    AdaptivePlanVersionRecord,
    PlannedWorkout,
    TrainingAdjustmentDraft,
    WeeklyReviewReport,
)
from planner_core.enums import WeeklyReviewStatus, WorkoutMainTypeNormalized, WorkoutStatusNormalized
from planner_core.weekly_review.schemas import WeeklyFactsRequest
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.adaptive_plan import AdaptiveApprovalResult
from server.observability.tracing import NOOP_TRACER, SafeTracer
from server.services.adaptive_plan_proposal_service import AdaptivePlanProposalService
from server.services.weekly_facts_service import WeeklyFactsService


COMPLETED = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}
ADAPTIVE_WEEKLY_PROPOSAL_SOURCES = {"weekly_review_v0130", "adaptive_weekly_coaching_v0164"}


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
    def __init__(self, tracer: SafeTracer | None = None) -> None:
        self.tracer = tracer or NOOP_TRACER

    @staticmethod
    def _revalidate_current_snapshot(
        db: Session,
        *,
        user_id: int,
        record: TrainingAdjustmentDraft,
        workouts: list[PlannedWorkout],
    ) -> None:
        """Re-check freshness and deterministic safety immediately before apply."""
        if record.review_report_id is None:
            return  # Backward-compatible v0.13 proposal without snapshot linkage.
        report = db.scalar(
            select(WeeklyReviewReport)
            .where(WeeklyReviewReport.id == record.review_report_id, WeeklyReviewReport.user_id == user_id)
            .with_for_update()
        )
        if report is None or report.weekly_facts_fingerprint is None:
            record.status = "invalidated"
            db.commit()
            raise BadRequestError("周复盘快照缺少可验证事实，请重新生成周复盘。", error_code="REVIEW_STALE")
        facts = WeeklyFactsService().build_weekly_facts(
            db,
            WeeklyFactsRequest(
                user_id=user_id,
                week_start=report.week_start_date,
                week_end=report.week_end_date,
                cycle_id=report.cycle_id,
                timezone="Asia/Shanghai",
            ),
        )
        if report.status != WeeklyReviewStatus.current or facts.result_hash != report.weekly_facts_fingerprint:
            report.status = WeeklyReviewStatus.stale
            record.status = "invalidated"
            db.commit()
            raise BadRequestError("本周训练事实已发生变化，请重新生成周复盘。", error_code="REVIEW_STALE")
        proposal = PlanAdjustmentProposal.model_validate({**record.adjustment_json, "user_id": user_id})
        by_id = {item.id: item for item in workouts}
        targets = [
            TargetPlanFact(
                plan_id=item.id,
                user_id=user_id,
                workout_date=item.workout_date,
                value=PlanValue(
                    content=item.planned_content,
                    distance_km=float(item.planned_distance_km) if item.planned_distance_km is not None else None,
                    main_type=item.main_type_normalized.value,
                    target_pace_text=item.target_pace_text,
                ),
                is_locked=item.is_locked,
                is_completed=bool(item.workout_log and item.workout_log.status_normalized in COMPLETED),
                plan_version=item.plan_version,
            )
            for item in workouts
        ]
        # Re-materializing only validates current deterministic facts; it never
        # invokes a provider or replaces the persisted candidate proposal.
        AdaptivePlanProposalService().create_proposal(
            user_id=user_id,
            weekly_facts=facts,
            target_plans=targets,
            candidates=[
                ProposalCandidateChange(
                    plan_id=change.plan_id,
                    action=change.action,
                    after=change.after,
                    reason=change.reason,
                    rule_evidence=change.rule_evidence,
                )
                for change in proposal.changes
                if change.plan_id in by_id
            ],
        )

    def persist_proposal(
        self,
        db: Session,
        *,
        user_id: int,
        proposal: PlanAdjustmentProposal,
        cycle_id: int | None = None,
        review_report_id: int | None = None,
        revision: int = 1,
        parent_proposal_id: int | None = None,
        feedback_json: dict | None = None,
        facts_hash: str | None = None,
    ) -> TrainingAdjustmentDraft:
        if proposal.user_id != user_id:
            raise BadRequestError("Proposal owner does not match the authenticated user.")
        record = TrainingAdjustmentDraft(
            user_id=user_id,
            cycle_id=cycle_id,
            week_start=proposal.week_start,
            status="pending_approval",
            source_type="adaptive_weekly_coaching_v0164" if review_report_id else "weekly_review_v0130",
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
            facts_hash=facts_hash,
            source_version="adaptive-weekly-coaching-1.0.0" if review_report_id else "adaptive-proposal-1.0.0",
            review_report_id=review_report_id,
            revision=revision,
            parent_proposal_id=parent_proposal_id,
            feedback_json=feedback_json,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def approve(self, db: Session, *, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
        trace = self.tracer.start_trace()
        with self.tracer.span(
            trace,
            component="approval",
            operation="approve_proposal",
            metadata={"proposal_id": proposal_id, "operation_type": "hitl_approval"},
            root=True,
        ):
            return self._approve(db, user_id=user_id, proposal_id=proposal_id, trace=trace)

    def _approve(
        self,
        db: Session,
        *,
        user_id: int,
        proposal_id: int,
        trace,
    ) -> AdaptiveApprovalResult:
        try:
            with self.tracer.span(
                trace,
                "proposal.validate",
                attributes={"proposal_id": proposal_id},
            ):
                record = db.scalar(
                    select(TrainingAdjustmentDraft)
                    .where(
                        TrainingAdjustmentDraft.id == proposal_id,
                        TrainingAdjustmentDraft.user_id == user_id,
                        TrainingAdjustmentDraft.source_type.in_(ADAPTIVE_WEEKLY_PROPOSAL_SOURCES),
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
            self._revalidate_current_snapshot(
                db,
                user_id=user_id,
                record=record,
                workouts=workouts,
            )
            before: list[dict] = []
            after: list[dict] = []
            with self.tracer.span(
                trace,
                "plan.apply",
                attributes={"plan_count": len(proposal.changes)},
            ):
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
            with self.tracer.span(
                trace,
                component="versioning",
                operation="create_plan_version",
                metadata={"operation_type": "plan_versioning"},
            ):
                db.add(version)
                db.flush()
                record.status = "applied"
                record.applied_result_json = {"version_id": version.id, "before": before, "after": after}
            with self.tracer.span(trace, "transaction"):
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
        trace = self.tracer.start_trace()
        with self.tracer.span(
            trace,
            component="approval",
            operation="reject_proposal",
            metadata={"proposal_id": proposal_id, "operation_type": "hitl_rejection"},
            root=True,
        ):
            return self._reject(db, user_id=user_id, proposal_id=proposal_id)

    @staticmethod
    def _reject(db: Session, *, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
        try:
            record = db.scalar(
                select(TrainingAdjustmentDraft)
                .where(
                    TrainingAdjustmentDraft.id == proposal_id,
                    TrainingAdjustmentDraft.user_id == user_id,
                    TrainingAdjustmentDraft.source_type.in_(ADAPTIVE_WEEKLY_PROPOSAL_SOURCES),
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
