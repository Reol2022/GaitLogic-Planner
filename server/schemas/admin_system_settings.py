from datetime import datetime

from pydantic import BaseModel

from planner_core.enums import AuthEntryMode


class PublicSystemSettingsRead(BaseModel):
    auth_entry_mode: AuthEntryMode
    allow_public_registration: bool


class AdminSystemSettingsRead(PublicSystemSettingsRead):
    id: int | None = None
    updated_at: datetime | None = None


class AdminSystemSettingsUpdate(BaseModel):
    auth_entry_mode: AuthEntryMode
    allow_public_registration: bool = True
