from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_db, require_admin_user
from server.schemas.admin_ai_settings import AdminAISettingsRead, AdminAISettingsUpdate
from server.schemas.admin_user import AdminUserRead, AdminUserUpdate
from server.services import admin_ai_settings_service, admin_user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ai-settings", response_model=AdminAISettingsRead)
def get_ai_settings(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return admin_ai_settings_service.get_admin_ai_settings(db)


@router.put("/ai-settings", response_model=AdminAISettingsRead)
def update_ai_settings(
    payload: AdminAISettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return admin_ai_settings_service.update_admin_ai_settings(db, payload, current_user.id)


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return admin_user_service.list_users(db, keyword)


@router.put("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(require_admin_user),
):
    return admin_user_service.update_user(db, user_id, payload, current_user.id)
