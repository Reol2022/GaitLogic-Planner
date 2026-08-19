from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin
from planner_core.enums import RecoveryCheckinSource
from server.integrations.activity_provider import ProviderRecoverySnapshot


_DAILY_STATE_FIELDS = ("sleep_duration_minutes", "resting_heart_rate_bpm", "hrv_value", "hrv_metric")


def apply_garmin_daily_health(
    db: Session, *, user_id: int, health: ProviderRecoverySnapshot
) -> tuple[DailyRecoveryCheckin, bool]:
    """Apply health facts to the existing DailyRecoveryCheckin for one date.

    This is deliberately part of Garmin activity sync, not a second recovery
    pipeline.  It writes only fields already consumed by daily-state rules.
    Explicit manual records retain their non-null objective values.
    """
    record = db.scalar(select(DailyRecoveryCheckin).where(
        DailyRecoveryCheckin.user_id == user_id,
        DailyRecoveryCheckin.checkin_date == health.recovery_date,
    ))
    if record is None:
        record = DailyRecoveryCheckin(
            user_id=user_id,
            checkin_date=health.recovery_date,
            source=RecoveryCheckinSource.garmin,
        )
        db.add(record)
    changed = False
    for field in _DAILY_STATE_FIELDS:
        incoming = getattr(health, field)
        if incoming is None:
            continue
        if record.source == RecoveryCheckinSource.manual and getattr(record, field) is not None:
            continue
        if getattr(record, field) != incoming:
            setattr(record, field, incoming)
            changed = True
    if health.hrv_value is not None and not (record.source == RecoveryCheckinSource.manual and record.hrv_source):
        record.hrv_source = "garmin"
    if record.source != RecoveryCheckinSource.manual:
        record.source = RecoveryCheckinSource.garmin
    return record, changed
