import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.common.response import MessageResponse
from server.schemas.auth import McpTokenResponse, TokenResponse, UserLogin, UserRead, UserRegister
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


@router.post("/mcp-token", response_model=McpTokenResponse)
def issue_mcp_token(current_user: UserAccount = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mint a short-lived MCP-only token for the already authenticated user.

    This endpoint is a GaitLogic provisioning helper, not an OAuth discovery or
    authorization-code flow.
    """

    from planner_core.config import get_settings

    settings = get_settings()
    from planner_core.database.models import McpOAuthGrant

    grant_id = secrets.token_urlsafe(32)
    resource = settings.mcp_resource_uri or f"{settings.mcp_public_base_url.rstrip('/')}/mcp"
    db.add(McpOAuthGrant(grant_id=grant_id, client_id="local-provisioning", user_id=current_user.id, resource_uri=resource))
    db.commit()
    return McpTokenResponse(
        access_token=auth_service.create_mcp_access_token(current_user, grant_id=grant_id),
        expires_in=settings.mcp_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=MessageResponse)
def logout():
    return MessageResponse(message="Logged out.")
