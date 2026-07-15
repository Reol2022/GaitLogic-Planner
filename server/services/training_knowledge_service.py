from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner_core.database.models import TrainingKnowledgeItem
from planner_core.training_knowledge.enums import KNOWLEDGE_CATEGORIES
from server.common.exceptions import NotFoundError


def list_categories() -> list[str]:
    return list(KNOWLEDGE_CATEGORIES)


def list_items(
    db: Session,
    *,
    is_admin: bool,
    category: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TrainingKnowledgeItem], int]:
    stmt = select(TrainingKnowledgeItem)
    count_stmt = select(func.count()).select_from(TrainingKnowledgeItem)
    predicates = []
    if not is_admin:
        predicates.append(TrainingKnowledgeItem.status == "active")
    elif status:
        predicates.append(TrainingKnowledgeItem.status == status)
    if category:
        predicates.append(TrainingKnowledgeItem.category == category)
    for predicate in predicates:
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(TrainingKnowledgeItem.category, TrainingKnowledgeItem.code)
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def get_item(db: Session, code: str, *, is_admin: bool) -> TrainingKnowledgeItem:
    stmt = select(TrainingKnowledgeItem).where(TrainingKnowledgeItem.code == code)
    if not is_admin:
        stmt = stmt.where(TrainingKnowledgeItem.status == "active")
    item = db.scalar(stmt)
    if item is None:
        raise NotFoundError("Training knowledge item not found.")
    return item

