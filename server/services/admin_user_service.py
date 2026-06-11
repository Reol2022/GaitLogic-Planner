from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.admin_user import AdminUserUpdate


def list_users(db: Session, keyword: str | None = None) -> list[UserAccount]:
    stmt = select(UserAccount)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                UserAccount.username.like(like),
                UserAccount.email.like(like),
                UserAccount.nickname.like(like),
            )
        )
    stmt = stmt.order_by(UserAccount.created_at.desc(), UserAccount.id.desc())
    return list(db.scalars(stmt))


def update_user(
    db: Session,
    user_id: int,
    payload: AdminUserUpdate,
    current_admin_id: int,
) -> UserAccount:
    user = db.get(UserAccount, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    if user.id == current_admin_id and (payload.role != "admin" or payload.status != "active"):
        raise BadRequestError("不能禁用当前管理员或移除自己的管理员权限。")

    user.email = payload.email
    user.nickname = payload.nickname
    user.role = payload.role
    user.status = payload.status
    db.commit()
    db.refresh(user)
    return user
