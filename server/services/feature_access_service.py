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
ROLLOUT_INHERIT = "inherit"
VALID_ROLLOUT_MODES = {ROLLOUT_OFF, ROLLOUT_ALLOWLIST, ROLLOUT_ALL}


def training_readiness_rollout_mode() -> str:
    mode = (get_settings().training_readiness_rollout_mode or ROLLOUT_OFF).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def workout_import_rollout_mode() -> str:
    mode = (get_settings().workout_import_rollout_mode or ROLLOUT_OFF).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def garmin_sync_rollout_mode() -> str:
    mode = (get_settings().garmin_sync_rollout_mode or ROLLOUT_OFF).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def data_sync_rollout_mode() -> str:
    mode = (get_settings().data_sync_rollout_mode or ROLLOUT_INHERIT).strip().lower()
    if mode == ROLLOUT_INHERIT:
        return garmin_sync_rollout_mode()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_OFF


def simplified_workflow_rollout_mode() -> str:
    mode = (get_settings().simplified_workflow_rollout_mode or ROLLOUT_ALL).strip().lower()
    return mode if mode in VALID_ROLLOUT_MODES else ROLLOUT_ALL


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


def _assert_rollout_available(db: Session, current_user: UserAccount, mode: str, feature_key: FeatureKey) -> None:
    if mode == ROLLOUT_OFF:
        raise NotFoundError("该功能当前未开放。", error_code="FEATURE_DISABLED")
    if mode == ROLLOUT_ALLOWLIST and not has_feature_access(db, current_user.id, feature_key):
        raise ForbiddenError("该功能当前处于灰度测试阶段。", error_code="FEATURE_NOT_AVAILABLE")


def assert_training_readiness_available(db: Session, current_user: UserAccount) -> None:
    _assert_rollout_available(db, current_user, training_readiness_rollout_mode(), FeatureKey.training_readiness)


def assert_workout_import_available(db: Session, current_user: UserAccount) -> None:
    _assert_rollout_available(db, current_user, workout_import_rollout_mode(), FeatureKey.workout_import)


def assert_garmin_sync_available(db: Session, current_user: UserAccount) -> None:
    _assert_rollout_available(db, current_user, garmin_sync_rollout_mode(), FeatureKey.garmin_sync)


def assert_data_sync_available(db: Session, current_user: UserAccount) -> None:
    _assert_rollout_available(db, current_user, data_sync_rollout_mode(), FeatureKey.garmin_sync)


def assert_simplified_workflow_available(db: Session, current_user: UserAccount) -> None:
    _assert_rollout_available(db, current_user, simplified_workflow_rollout_mode(), FeatureKey.simplified_workflow)
