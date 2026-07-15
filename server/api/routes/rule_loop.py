from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.training_rule_loop import (
    DraftValidationRequest,
    PlanValidationRequest,
    RuleLoopEvaluationResponse,
    TodayEvaluationResponse,
    TrainingAdjustmentApplyResponse,
    TrainingAdjustmentDraftListResponse,
    TrainingAdjustmentDraftRead,
)
from server.services import training_rule_loop_service
from server.services.weekly_review_stats_service import local_today

router = APIRouter(tags=["rule loop"])


@router.post("/training-rules/validate-plan", response_model=RuleLoopEvaluationResponse)
def validate_plan(
    payload: PlanValidationRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.validate_cycle_plan(db, current_user.id, payload.cycle_id, force=payload.force)


@router.post("/training-plans/{cycle_id}/validate", response_model=RuleLoopEvaluationResponse)
def validate_training_plan(
    cycle_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.validate_cycle_plan(db, current_user.id, cycle_id, force=force)


@router.get("/training-plans/{cycle_id}/latest-validation", response_model=RuleLoopEvaluationResponse)
def latest_training_plan_validation(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.validate_cycle_plan(db, current_user.id, cycle_id, force=False)


@router.post("/ai-plan-drafts/{draft_id}/validate", response_model=RuleLoopEvaluationResponse)
def validate_ai_plan_draft(
    draft_id: int,
    payload: DraftValidationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.validate_ai_plan_draft(
        db,
        current_user.id,
        draft_id,
        force=bool(payload.force if payload else False),
    )


@router.post("/plan-import-drafts/{import_id}/validate", response_model=RuleLoopEvaluationResponse)
def validate_plan_import_draft(
    import_id: int,
    payload: DraftValidationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.validate_plan_import_draft(
        db,
        current_user.id,
        import_id,
        force=bool(payload.force if payload else False),
    )


@router.get("/training-readiness/today-evaluation", response_model=TodayEvaluationResponse)
def get_today_evaluation(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_today(db, current_user.id, date_ or local_today(), force=False)


@router.post("/training-readiness/today-evaluation", response_model=TodayEvaluationResponse)
def create_today_evaluation(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_today(db, current_user.id, date_ or local_today(), force=False)


@router.post("/training-readiness/today-evaluation/recalculate", response_model=TodayEvaluationResponse)
def recalculate_today_evaluation(
    date_: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_today(db, current_user.id, date_ or local_today(), force=True)


@router.post("/workout-logs/{workout_log_id}/rule-review", response_model=RuleLoopEvaluationResponse)
def create_workout_rule_review(
    workout_log_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.review_workout_log(db, current_user.id, workout_log_id, force=force)


@router.get("/workout-logs/{workout_log_id}/rule-review", response_model=RuleLoopEvaluationResponse)
def get_workout_rule_review(
    workout_log_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.review_workout_log(db, current_user.id, workout_log_id, force=False)


@router.post("/weekly-reviews/{review_id}/rule-evaluation", response_model=RuleLoopEvaluationResponse)
def weekly_rule_evaluation_from_review(
    review_id: int,
    cycle_id: int = Query(...),
    source_block_id: int = Query(...),
    target_block_id: int | None = Query(default=None),
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_weekly_rules(
        db,
        current_user.id,
        cycle_id,
        source_block_id,
        target_block_id,
        force=force,
    )


@router.get("/weekly-reviews/{review_id}/rule-evaluation", response_model=RuleLoopEvaluationResponse)
def get_weekly_rule_evaluation_from_review(
    review_id: int,
    cycle_id: int = Query(...),
    source_block_id: int = Query(...),
    target_block_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_weekly_rules(
        db,
        current_user.id,
        cycle_id,
        source_block_id,
        target_block_id,
        force=False,
    )


@router.post("/weekly-reviews/{review_id}/adjustment-draft", response_model=RuleLoopEvaluationResponse)
def weekly_adjustment_draft(
    review_id: int,
    cycle_id: int = Query(...),
    source_block_id: int = Query(...),
    target_block_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.evaluate_weekly_rules(
        db,
        current_user.id,
        cycle_id,
        source_block_id,
        target_block_id,
        force=False,
    )


@router.get("/training-adjustment-drafts", response_model=TrainingAdjustmentDraftListResponse)
def list_adjustment_drafts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    items, total = training_rule_loop_service.list_adjustment_drafts(db, current_user.id, limit=limit, offset=offset)
    return TrainingAdjustmentDraftListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/training-adjustment-drafts/{draft_id}", response_model=TrainingAdjustmentDraftRead)
def get_adjustment_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.get_adjustment_draft(db, current_user.id, draft_id)


@router.post("/training-adjustment-drafts/{draft_id}/confirm", response_model=TrainingAdjustmentDraftRead)
def confirm_adjustment_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.confirm_adjustment_draft(db, current_user.id, draft_id)


@router.post("/training-adjustment-drafts/{draft_id}/apply", response_model=TrainingAdjustmentApplyResponse)
def apply_adjustment_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    draft = training_rule_loop_service.apply_adjustment_draft(db, current_user.id, draft_id)
    return TrainingAdjustmentApplyResponse(draft_id=draft.id, status=draft.status, applied_result=draft.applied_result_json or {})


@router.post("/training-adjustment-drafts/{draft_id}/reject", response_model=TrainingAdjustmentDraftRead)
def reject_adjustment_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_loop_service.reject_adjustment_draft(db, current_user.id, draft_id)
