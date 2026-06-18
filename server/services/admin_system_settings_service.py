from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import AdminSystemSettings
from server.schemas.admin_system_settings import (
    AdminSystemSettingsRead,
    AdminSystemSettingsUpdate,
    PublicSystemSettingsRead,
)

SETTINGS_ROW_ID = 1


def get_or_create_admin_system_settings(db: Session) -> AdminSystemSettings:
    row = db.scalar(select(AdminSystemSettings).where(AdminSystemSettings.id == SETTINGS_ROW_ID))
    if row is not None:
        return row

    row = AdminSystemSettings(id=SETTINGS_ROW_ID)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def to_public_schema(row: AdminSystemSettings) -> PublicSystemSettingsRead:
    return PublicSystemSettingsRead(
        auth_entry_mode=row.auth_entry_mode,
        allow_public_registration=bool(row.allow_public_registration),
    )


def to_admin_schema(row: AdminSystemSettings) -> AdminSystemSettingsRead:
    return AdminSystemSettingsRead(
        id=row.id,
        auth_entry_mode=row.auth_entry_mode,
        allow_public_registration=bool(row.allow_public_registration),
        updated_at=row.updated_at,
    )


def get_public_system_settings(db: Session) -> PublicSystemSettingsRead:
    return to_public_schema(get_or_create_admin_system_settings(db))


def get_admin_system_settings(db: Session) -> AdminSystemSettingsRead:
    return to_admin_schema(get_or_create_admin_system_settings(db))


def update_admin_system_settings(
    db: Session,
    payload: AdminSystemSettingsUpdate,
    admin_user_id: int,
) -> AdminSystemSettingsRead:
    row = get_or_create_admin_system_settings(db)
    row.auth_entry_mode = payload.auth_entry_mode
    row.allow_public_registration = payload.allow_public_registration
    row.updated_by_id = admin_user_id
    db.commit()
    db.refresh(row)
    return to_admin_schema(row)
