from collections.abc import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.common.exceptions import ForbiddenError, UnauthorizedError
from server.services.auth_service import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db() -> Generator[Session, None, None]:
    from planner_core.database.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload.")
    user = db.scalar(select(UserAccount).where(UserAccount.id == int(user_id)))
    if user is None or user.status != "active":
        raise UnauthorizedError("User account is not available.")
    return user


def require_admin_user(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:
    if current_user.role != "admin":
        raise ForbiddenError("Admin permission required.")
    return current_user
