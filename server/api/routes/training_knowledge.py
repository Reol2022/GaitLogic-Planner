from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.training_knowledge import (
    TrainingKnowledgeCategoriesResponse,
    TrainingKnowledgeItemRead,
    TrainingKnowledgeItemsResponse,
)
from server.services import training_knowledge_service

router = APIRouter(prefix="/training-knowledge", tags=["training knowledge"])


@router.get("/categories", response_model=TrainingKnowledgeCategoriesResponse)
def categories(current_user: UserAccount = Depends(get_current_user)):
    return TrainingKnowledgeCategoriesResponse(categories=training_knowledge_service.list_categories())


@router.get("/items", response_model=TrainingKnowledgeItemsResponse)
def list_items(
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    items, total = training_knowledge_service.list_items(
        db,
        is_admin=current_user.role == "admin",
        category=category,
        status=status,
        limit=limit,
        offset=offset,
    )
    return TrainingKnowledgeItemsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/items/{code}", response_model=TrainingKnowledgeItemRead)
def get_item(
    code: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    return training_knowledge_service.get_item(db, code, is_admin=current_user.role == "admin")

