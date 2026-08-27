"""Revision lifecycle for immutable weekly-review snapshots.

Review Snapshot is immutable analysis history. Proposal is mutable/versioned
candidate state. Safety-critical facts are revalidated at proposal/apply time.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.adaptive_plan.schemas import PlanAdjustmentProposal, PlanValue, TargetPlanFact
from planner_core.config import get_settings
from planner_core.database.models import PlannedWorkout, TrainingAdjustmentDraft, WeeklyReviewReport
from planner_core.enums import TrainingStatus, WeeklyReviewStatus, WorkoutStatusNormalized
from planner_core.weekly_review.schemas import WeeklyFactsRequest
from server.common.exceptions import BadRequestError, NotFoundError
from server.domain.decision_readiness import DomainReadiness
from server.schemas.adaptive_plan import (
    AdaptiveProposalRead,
    ProposalFeedbackReason,
    ProposalRevisionFeedback,
    ProposalRevisionResult,
)
from server.services.adaptive_plan_approval_service import (
    ADAPTIVE_WEEKLY_PROPOSAL_SOURCES,
    AdaptivePlanApprovalService,
)
from server.services.admin_ai_settings_service import get_effective_ai_settings
from server.services.weekly_facts_service import WeeklyFactsService
from server.structured_task_provider import StructuredTaskProvider
from server.weekly_review_graph.adapters import (
    DeterministicProposalMaterializer,
    StructuredPlanDesigner,
)
from server.weekly_review_graph.schemas import WeeklyReviewAnalysis, WeeklyReviewState


COMPLETED = {
    WorkoutStatusNormalized.completed_high,
    WorkoutStatusNormalized.completed_normal,
    WorkoutStatusNormalized.completed_adjusted,
}


def _proposal_read(record: TrainingAdjustmentDraft) -> AdaptiveProposalRead:
    return AdaptiveProposalRead(
        id=record.id,
        week_start=record.week_start,
        status=record.status,
        proposal=record.adjustment_json,
        review_report_id=record.review_report_id,
        revision=record.revision,
        parent_proposal_id=record.parent_proposal_id,
        feedback=record.feedback_json,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class AdaptiveWeeklyCoachingService:
    """Generate proposal revisions without recomputing Weekly Review analysis."""

    def __init__(self, facts_service: WeeklyFactsService | None = None) -> None:
        self.facts_service = facts_service or WeeklyFactsService()

    @staticmethod
    def persist_review_snapshot(
        db: Session,
        *,
        user_id: int,
        cycle_id: int,
        source_block_id: int,
        target_block_id: int | None,
        state: WeeklyReviewState,
    ) -> WeeklyReviewReport:
        """Persist only once, after the full Review graph has completed.

        No revision path calls this method: a snapshot is immutable analysis
        history and a newer snapshot supersedes the prior current one.
        """
        if state.weekly_facts is None or state.weekly_analysis is None:
            raise BadRequestError("Completed weekly facts and analysis are required.")
        prior_reports = list(
            db.scalars(
                select(WeeklyReviewReport)
                .where(
                    WeeklyReviewReport.user_id == user_id,
                    WeeklyReviewReport.source_block_id == source_block_id,
                    WeeklyReviewReport.target_block_id == target_block_id,
                )
                .with_for_update()
            )
        )
        for item in prior_reports:
            if item.status == WeeklyReviewStatus.current:
                item.status = WeeklyReviewStatus.superseded
        facts = state.weekly_facts
        primary = facts.classification.primary_status.value
        training_status = (
            TrainingStatus.reduce_load if primary == "RECOVERY_CONCERN"
            else TrainingStatus.watch if primary in {"OVER_COMPLETED", "INTENSITY_IMBALANCE", "MIXED"}
            else TrainingStatus.normal if primary == "ON_TRACK"
            else TrainingStatus.insufficient_data
        )
        report = WeeklyReviewReport(
            user_id=user_id,
            cycle_id=cycle_id,
            source_block_id=source_block_id,
            target_block_id=target_block_id,
            week_start_date=facts.period.week_start,
            week_end_date=facts.period.week_end,
            version=(max((item.version for item in prior_reports), default=0) + 1),
            status=WeeklyReviewStatus.current,
            training_status=training_status,
            metrics_json=facts.model_dump(mode="json"),
            rule_reasons_json=list(facts.classification.rule_codes),
            missing_data_json=list(facts.classification.limitations),
            summary=state.weekly_analysis.overall_assessment,
            positive_points_json=state.weekly_analysis.positive_signals,
            attention_points_json=state.weekly_analysis.risk_signals,
            next_week_strategy=state.weekly_analysis.recommended_direction[0] if state.weekly_analysis.recommended_direction else None,
            risk_notes_json=state.weekly_analysis.warnings,
            source_snapshot_json={"weekly_facts": facts.model_dump(mode="json")},
            snapshot_hash=facts.result_hash,
            weekly_facts_fingerprint=facts.result_hash,
            analysis_snapshot_json=state.weekly_analysis.model_dump(mode="json"),
            readiness_snapshot_json=[item.model_dump(mode="json") for item in state.decision_readiness],
            evidence_snapshot_json={
                "fingerprint": state.evidence_fingerprint,
                "status": {item.domain: item.status.value for item in state.evidence_assessments},
            },
            knowledge_references_json=[item.model_dump(mode="json") for item in state.knowledge_results],
            algorithm_version="adaptive-weekly-coaching-v0164",
            prompt_version="weekly-review-analysis-v1",
            model_name=None,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def _targets(db: Session, *, user_id: int, report: WeeklyReviewReport) -> list[TargetPlanFact]:
        if report.target_block_id is None:
            raise BadRequestError("Review has no target training week for proposal revision.")
        rows = list(
            db.scalars(
                select(PlannedWorkout)
                .options(selectinload(PlannedWorkout.workout_log))
                .where(
                    PlannedWorkout.user_id == user_id,
                    PlannedWorkout.block_id == report.target_block_id,
                )
                .order_by(PlannedWorkout.workout_date, PlannedWorkout.sort_order, PlannedWorkout.id)
            )
        )
        return [
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
            for item in rows
        ]

    def _current_facts(self, db: Session, *, user_id: int, report: WeeklyReviewReport):
        return self.facts_service.build_weekly_facts(
            db,
            WeeklyFactsRequest(
                user_id=user_id,
                week_start=report.week_start_date,
                week_end=report.week_end_date,
                cycle_id=report.cycle_id,
                timezone="Asia/Shanghai",
            ),
        )

    @staticmethod
    def _feedback_payload(feedback: ProposalRevisionFeedback) -> dict:
        # Only low-cardinality codes enter traceable/persisted metadata.  The
        # free-text preference is supplied to Plan Design but never becomes rule
        # evidence or a bypass for deterministic safety validation.
        return {
            "reason_codes": [item.value for item in feedback.reason_codes],
            "free_text": feedback.free_text.strip() if feedback.free_text else None,
        }

    def revise_proposal(
        self,
        db: Session,
        *,
        user_id: int,
        review_id: int,
        proposal_id: int,
        feedback: ProposalRevisionFeedback,
    ) -> ProposalRevisionResult:
        report = db.scalar(
            select(WeeklyReviewReport)
            .where(WeeklyReviewReport.id == review_id, WeeklyReviewReport.user_id == user_id)
            .with_for_update()
        )
        if report is None:
            raise NotFoundError("Weekly review snapshot not found.")
        previous = db.scalar(
            select(TrainingAdjustmentDraft)
            .where(
                TrainingAdjustmentDraft.id == proposal_id,
                TrainingAdjustmentDraft.user_id == user_id,
                TrainingAdjustmentDraft.review_report_id == report.id,
                TrainingAdjustmentDraft.source_type.in_(ADAPTIVE_WEEKLY_PROPOSAL_SOURCES),
            )
            .with_for_update()
        )
        if previous is None:
            raise NotFoundError("Adaptive proposal not found for this weekly review.")

        # Replay protection: one parent proposal can materialize at most one
        # direct child revision, regardless of a duplicated HTTP resume.
        existing_child = db.scalar(
            select(TrainingAdjustmentDraft)
            .where(
                TrainingAdjustmentDraft.parent_proposal_id == previous.id,
                TrainingAdjustmentDraft.user_id == user_id,
            )
            .order_by(TrainingAdjustmentDraft.id.desc())
            .limit(1)
        )
        if existing_child is not None:
            return ProposalRevisionResult(
                status="PENDING_APPROVAL",
                proposal=_proposal_read(existing_child),
                revision_limit=get_settings().max_proposal_revisions,
            )

        if report.weekly_facts_fingerprint is None or report.analysis_snapshot_json is None:
            # Legacy records are intentionally never assumed fresh.
            report.status = WeeklyReviewStatus.stale
            previous.status = "invalidated"
            db.commit()
            return ProposalRevisionResult(status="REVIEW_STALE", revision_limit=get_settings().max_proposal_revisions)

        facts = self._current_facts(db, user_id=user_id, report=report)
        if report.status != WeeklyReviewStatus.current or facts.result_hash != report.weekly_facts_fingerprint:
            report.status = WeeklyReviewStatus.stale
            if previous.status == "pending_approval":
                previous.status = "invalidated"
            db.commit()
            return ProposalRevisionResult(status="REVIEW_STALE", revision_limit=get_settings().max_proposal_revisions)

        settings = get_settings()
        if previous.revision - 1 >= settings.max_proposal_revisions:
            if previous.status == "pending_approval":
                previous.status = "rejected"
                db.commit()
            return ProposalRevisionResult(status="REVISION_LIMIT_REACHED", revision_limit=settings.max_proposal_revisions)
        if previous.status != "pending_approval":
            raise BadRequestError("Only a pending proposal can be revised.")

        analysis = WeeklyReviewAnalysis.model_validate(report.analysis_snapshot_json)
        readiness = [
            DomainReadiness.model_validate(item)
            for item in (report.readiness_snapshot_json or [])
        ]
        targets = self._targets(db, user_id=user_id, report=report)
        runtime = get_effective_ai_settings(db)
        provider_settings = settings.model_copy(
            update={
                "ai_api_key": runtime.ai_api_key,
                "deepseek_base_url": runtime.ai_base_url,
                "deepseek_model": runtime.ai_model,
                "deepseek_timeout_seconds": runtime.ai_timeout_seconds,
            }
        )
        provider = StructuredTaskProvider(provider_settings)
        feedback_payload = self._feedback_payload(feedback)
        state = WeeklyReviewState(
            user_id=user_id,
            request=WeeklyFactsRequest(
                user_id=user_id,
                week_start=report.week_start_date,
                week_end=report.week_end_date,
                cycle_id=report.cycle_id,
                timezone="Asia/Shanghai",
            ),
            weekly_facts=facts,
            rule_results=list(facts.classification.rule_codes),
            decision_readiness=readiness,
            target_plans=targets,
            weekly_analysis=analysis,
            previous_proposal=PlanAdjustmentProposal.model_validate(
                {**previous.adjustment_json, "user_id": user_id}
            ),
            revision_feedback=feedback_payload,
            revision_number=previous.revision + 1,
        )
        # The sole provider call in a revision is PLAN_DESIGN. Materialization
        # and validation remain deterministic and execute for every revision.
        design = StructuredPlanDesigner(provider, provider_settings, db=db)(state)
        state.plan_design = design
        proposal = DeterministicProposalMaterializer()(state)
        previous.status = "rejected"
        record = AdaptivePlanApprovalService().persist_proposal(
            db,
            user_id=user_id,
            proposal=proposal,
            cycle_id=report.cycle_id,
            review_report_id=report.id,
            revision=previous.revision + 1,
            parent_proposal_id=previous.id,
            feedback_json=feedback_payload,
            facts_hash=facts.result_hash,
        )
        return ProposalRevisionResult(
            status="PENDING_APPROVAL",
            proposal=_proposal_read(record),
            revision_limit=settings.max_proposal_revisions,
        )
