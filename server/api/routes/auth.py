from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister
from server.services import admin_system_settings_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    settings = admin_system_settings_service.get_public_system_settings(db)
    if not settings.allow_public_registration:
        from server.common.exceptions import ForbiddenError

        raise ForbiddenError("Public registration is disabled.")
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    return auth_service.authenticate_user(db, payload)


@router.get("/me", response_model=UserRead)
def me(current_user: UserAccount = Depends(get_current_user)):
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout():
    return MessageResponse(message="Logged out.")
