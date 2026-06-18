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
from server.services.training_status_service import evaluate_training_status
from server.services.weekly_review_stats_service import build_weekly_review_metrics

router = APIRouter(tags=["weekly reviews"])


@router.get("/weekly-reviews/summary", response_model=WeeklyReviewSummaryResponse)
def get_weekly_review_summary(
    cycle_id: int = Query(...),
    block_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    metrics = build_weekly_review_metrics(db, current_user.id, cycle_id, block_id)
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
