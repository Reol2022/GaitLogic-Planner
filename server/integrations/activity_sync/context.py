from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount


@dataclass(slots=True)
class DataSyncContext:
    db: Session
    current_user: UserAccount
    provider_key: str | None = None
