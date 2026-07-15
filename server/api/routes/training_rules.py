from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from planner_core.training_knowledge.loaders import load_repository
from server.api.deps import get_current_user, get_db, require_admin_user
from server.schemas.training_rules import (
    TrainingRuleEnabledUpdate,
    TrainingRuleEvaluateRequest,
    TrainingRuleEvaluateResponse,
    TrainingRuleEvaluationDetail,
    TrainingRuleEvaluationsResponse,
    TrainingRuleRead,
    TrainingRulesResponse,
    TrainingRuleSyncResponse,
    TrainingRuleValidateRequest,
    TrainingRuleValidateResponse,
)
from server.services import training_rule_service, training_rule_sync_service

router = APIRouter(prefix="/training-rules", tags=["training rules"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@router.get("", response_model=TrainingRulesResponse)
def list_rules(
    category: str | None = None,
    scope: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    items, total = training_rule_service.list_rules(
        db,
        is_admin=current_user.role == "admin",
        category=category,
        scope=scope,
        severity=severity,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )
    return TrainingRulesResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/evaluate", response_model=TrainingRuleEvaluateResponse)
def evaluate(
    payload: TrainingRuleEvaluateRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_service.evaluate_rules(db, user_id=current_user.id, payload=payload)


@router.get("/evaluations", response_model=TrainingRuleEvaluationsResponse)
def list_evaluations(
    context_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    items, total = training_rule_service.list_evaluations(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == "admin",
        context_type=context_type,
        limit=limit,
        offset=offset,
    )
    return TrainingRuleEvaluationsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/evaluations/{evaluation_id}", response_model=TrainingRuleEvaluationDetail)
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_service.get_evaluation(
        db,
        evaluation_id,
        user_id=current_user.id,
        is_admin=current_user.role == "admin",
    )


@router.patch("/{code}/enabled", response_model=TrainingRuleRead)
def set_enabled(
    code: str,
    payload: TrainingRuleEnabledUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return training_rule_service.set_rule_enabled(db, code, payload.enabled)


@router.post("/validate-definition", response_model=TrainingRuleValidateResponse)
def validate_definition(
    payload: TrainingRuleValidateRequest,
    current_user: UserAccount = Depends(require_admin_user),
):
    rule = training_rule_service.validate_rule_payload(payload.definition)
    return TrainingRuleValidateResponse(valid=True, rule=rule)


@router.post("/sync", response_model=TrainingRuleSyncResponse, status_code=status.HTTP_200_OK)
def sync_rules(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    counters = training_rule_sync_service.sync_repository(db, PROJECT_ROOT)
    return TrainingRuleSyncResponse(**counters)


@router.get("/{code}", response_model=TrainingRuleRead)
def get_rule(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_rule_service.get_rule(db, code, is_admin=current_user.role == "admin")

