from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.weekly_review import (
    PlanAdjustmentApplyRequest,
    PlanAdjustmentApplyResponse,
    PlanAdjustmentItemUpdate,
    WeeklyReviewDetailResponse,
    WeeklyReviewGenerateRequest,
    WeeklyReviewListResponse,
    WeeklyReviewSummaryResponse,
)
from server.services import plan_adjustment_apply_service, weekly_review_ai_service
from server.services import readiness_assessment_service
from server.services.training_status_service import evaluate_training_status
from server.services.training_load_service import build_training_load_summary
from server.services.weekly_review_stats_service import build_weekly_review_metrics, local_today
from server.schemas.adaptive_plan import (
    AdaptiveApprovalResult,
    AdaptivePlanVersionList,
    AdaptivePlanVersionRead,
    AdaptiveProposalRead,
    PlanRollbackRequest,
)
from server.services.adaptive_plan_approval_service import AdaptivePlanApprovalService
from server.services.adaptive_plan_version_service import AdaptivePlanVersionService
from planner_core.database.models import TrainingAdjustmentDraft
from sqlalchemy import select
from server.common.exceptions import NotFoundError

router = APIRouter(tags=["weekly reviews"])
adaptive_approval_service = AdaptivePlanApprovalService()
adaptive_version_service = AdaptivePlanVersionService()


@router.get("/weekly-reviews/summary", response_model=WeeklyReviewSummaryResponse)
def get_weekly_review_summary(
    cycle_id: int = Query(...),
    block_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    metrics = build_weekly_review_metrics(db, current_user.id, cycle_id, block_id)
    assessment_date = min(metrics.week_end_date, local_today())
    load_summary = build_training_load_summary(db, current_user.id, assessment_date)
    readiness = readiness_assessment_service.get_latest_assessment(db, current_user.id, assessment_date)
    metrics.rolling_7d_srpe_load_au = load_summary.rolling_7d_srpe_load_au
    metrics.baseline_28d_weekly_srpe_load_au = load_summary.baseline_28d_weekly_srpe_load_au
    metrics.recent_to_baseline_load_ratio = load_summary.recent_to_baseline_load_ratio
    metrics.recovery_checkin_coverage_ratio = load_summary.recovery_checkin_coverage_ratio
    metrics.readiness_data_quality = readiness.data_quality.value if readiness else None
    metrics.readiness_status = readiness.status if readiness else None
    return WeeklyReviewSummaryResponse(metrics=metrics, training_status=evaluate_training_status(metrics))


@router.post("/weekly-reviews/generate", response_model=WeeklyReviewDetailResponse)
def generate_weekly_review(
    payload: WeeklyReviewGenerateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return weekly_review_ai_service.generate_weekly_review(
        db,
        current_user.id,
        payload.cycle_id,
        payload.source_block_id,
        payload.target_block_id,
    )


@router.get("/weekly-reviews", response_model=WeeklyReviewListResponse)
def list_weekly_reviews(
    cycle_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return weekly_review_ai_service.list_weekly_reviews(db, current_user.id, cycle_id, page, page_size)


@router.get("/weekly-reviews/{review_id}", response_model=WeeklyReviewDetailResponse)
def get_weekly_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return weekly_review_ai_service.get_weekly_review_detail(db, current_user.id, review_id)


@router.patch(
    "/plan-adjustment-drafts/{draft_id}/items/{item_id}",
    response_model=WeeklyReviewDetailResponse,
)
def update_adjustment_item(
    draft_id: int,
    item_id: int,
    payload: PlanAdjustmentItemUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    item = plan_adjustment_apply_service.update_adjustment_item(
        db, current_user.id, draft_id, item_id, payload
    )
    draft = item.draft
    return weekly_review_ai_service.get_weekly_review_detail(db, current_user.id, draft.review_report_id)


@router.post(
    "/plan-adjustment-drafts/{draft_id}/apply",
    response_model=PlanAdjustmentApplyResponse,
)
def apply_adjustment_draft(
    draft_id: int,
    payload: PlanAdjustmentApplyRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return plan_adjustment_apply_service.apply_adjustment_draft(
        db, current_user.id, draft_id, payload.selected_item_ids
    )


@router.post(
    "/plan-adjustment-drafts/{draft_id}/reject",
    response_model=WeeklyReviewDetailResponse,
)
def reject_adjustment_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    draft = plan_adjustment_apply_service.reject_adjustment_draft(db, current_user.id, draft_id)
    return weekly_review_ai_service.get_weekly_review_detail(db, current_user.id, draft.review_report_id)


@router.get("/adaptive-plan/proposals/{proposal_id}", response_model=AdaptiveProposalRead)
def get_adaptive_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    record = db.scalar(
        select(TrainingAdjustmentDraft).where(
            TrainingAdjustmentDraft.id == proposal_id,
            TrainingAdjustmentDraft.user_id == current_user.id,
            TrainingAdjustmentDraft.source_type == "weekly_review_v0130",
        )
    )
    if record is None:
        raise NotFoundError("Adaptive proposal not found.")
    return AdaptiveProposalRead(
        id=record.id,
        week_start=record.week_start,
        status=record.status,
        proposal=record.adjustment_json,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/adaptive-plan/proposals/{proposal_id}/approve",
    response_model=AdaptiveApprovalResult,
)
def approve_adaptive_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return adaptive_approval_service.approve(
        db, user_id=current_user.id, proposal_id=proposal_id
    )


@router.post(
    "/adaptive-plan/proposals/{proposal_id}/reject",
    response_model=AdaptiveApprovalResult,
)
def reject_adaptive_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return adaptive_approval_service.reject(
        db, user_id=current_user.id, proposal_id=proposal_id
    )


@router.get("/adaptive-plan/versions", response_model=AdaptivePlanVersionList)
def list_adaptive_plan_versions(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return AdaptivePlanVersionList(
        items=[
            AdaptivePlanVersionRead.model_validate(item)
            for item in adaptive_version_service.list_versions(db, user_id=current_user.id)
        ]
    )


@router.post(
    "/adaptive-plan/versions/{version_id}/rollback",
    response_model=AdaptivePlanVersionRead,
)
def rollback_adaptive_plan_version(
    version_id: int,
    payload: PlanRollbackRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return AdaptivePlanVersionRead.model_validate(
        adaptive_version_service.rollback(
            db,
            user_id=current_user.id,
            version_id=version_id,
            reason=payload.reason,
        )
    )
