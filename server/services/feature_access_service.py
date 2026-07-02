from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import FeatureAccess, UserAccount
from planner_core.enums import FeatureKey
from server.common.exceptions import ForbiddenError, NotFoundError

ROLLOUT_OFF = "off"
ROLLOUT_ALLOWLIST = "allowlist"
ROLLOUT_ALL = "all"
VALID_ROLLOUT_MODES = {ROLLOUT_OFF, ROLLOUT_ALLOWLIST, ROLLOUT_ALL}


def training_readiness_rollout_mode() -> str:
    mode = (get_settings().training_readiness_rollout_mode or ROLLOUT_OFF).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def workout_import_rollout_mode() -> str:
    mode = (get_settings().workout_import_rollout_mode or ROLLOUT_OFF).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def has_feature_access(db: Session, user_id: int, feature_key: FeatureKey) -> bool:
    access = db.scalar(
        select(FeatureAccess).where(
            FeatureAccess.user_id == user_id,
            FeatureAccess.feature_key == feature_key,
            FeatureAccess.enabled.is_(True),
        )
    )
    if access is None:
        return False
    return access.expires_at is None or access.expires_at > datetime.utcnow()


def assert_training_readiness_available(db: Session, current_user: UserAccount) -> None:
    mode = training_readiness_rollout_mode()
    if mode == ROLLOUT_OFF:
        raise NotFoundError("该功能当前未开放", error_code="FEATURE_DISABLED")
    if mode == ROLLOUT_ALLOWLIST and not has_feature_access(
        db, current_user.id, FeatureKey.training_readiness
    ):
        raise ForbiddenError("该功能当前处于灰度测试阶段", error_code="FEATURE_NOT_AVAILABLE")


def assert_workout_import_available(db: Session, current_user: UserAccount) -> None:
    mode = workout_import_rollout_mode()
    if mode == ROLLOUT_OFF:
        raise NotFoundError("该功能当前未开放", error_code="FEATURE_DISABLED")
    if mode == ROLLOUT_ALLOWLIST and not has_feature_access(
        db, current_user.id, FeatureKey.workout_import
    ):
        raise ForbiddenError("该功能当前处于灰度测试阶段", error_code="FEATURE_NOT_AVAILABLE")
