from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.simplified_workflow import TaskListResponse
from server.services import task_center_service
from server.services.feature_access_service import assert_simplified_workflow_available

router = APIRouter(prefix="/todos", tags=["task center"])


@router.get("", response_model=TaskListResponse)
def list_todos(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> TaskListResponse:
    assert_simplified_workflow_available(db, current_user)
    items = task_center_service.list_tasks(db, current_user.id, limit)
    return TaskListResponse(items=items, total=len(items))


@router.patch("/{task_key}", response_model=TaskListResponse)
def update_todo_state(
    task_key: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> TaskListResponse:
    assert_simplified_workflow_available(db, current_user)
    # v0.9.5 uses real-time aggregation. Persistent read/snooze state can be
    # added later via user_task_state without changing this endpoint.
    items = [item for item in task_center_service.list_tasks(db, current_user.id, limit) if item.task_key != task_key]
    return TaskListResponse(items=items, total=len(items))
