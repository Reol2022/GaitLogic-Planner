from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin
from planner_core.enums import RecoveryCheckinSource
from server.integrations.activity_provider import ProviderRecoverySnapshot


_GARMIN_FIELDS = (
    "sleep_duration_minutes",
    "resting_heart_rate_bpm",
    "hrv_value",
    "hrv_metric",
    "sleep_score",
    "average_stress",
    "max_stress",
    "body_battery_start",
    "body_battery_end",
    "body_battery_high",
    "body_battery_low",
    "respiration_rate",
    "pulse_ox",
    "provider_updated_at",
)
_FIELD_SOURCES = {
    "sleep_duration_minutes": "sleep_source",
    "resting_heart_rate_bpm": "resting_heart_rate_source",
    "hrv_value": "hrv_source",
    "hrv_metric": "hrv_source",
}


def apply_garmin_daily_health(
    db: Session, *, user_id: int, health: ProviderRecoverySnapshot
) -> tuple[DailyRecoveryCheckin, bool]:
    """Apply health facts to the existing DailyRecoveryCheckin for one date.

    This is deliberately part of Garmin activity sync, not a second recovery
    pipeline. It writes normalized facts into the existing daily-state model.
    Explicit manual objective values retain precedence field by field. Updating
    a subjective field no longer freezes every Garmin objective metric.
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
    for field in _GARMIN_FIELDS:
        incoming = getattr(health, field)
        if incoming is None:
            continue
        source_field = _FIELD_SOURCES.get(field)
        if source_field and getattr(record, source_field) == "manual" and getattr(record, field) is not None:
            continue
        if getattr(record, field) != incoming:
            setattr(record, field, incoming)
            changed = True
        if source_field and getattr(record, source_field) != "manual":
            setattr(record, source_field, "garmin")

    now = datetime.utcnow()
    has_device_metric = any(
        getattr(health, field) is not None
        for field in _GARMIN_FIELDS
        if field != "provider_updated_at"
    )
    status = (
        "UNAVAILABLE"
        if not has_device_metric
        else "PARTIAL"
        if health.missing_fields
        else "AVAILABLE"
    )
    metadata = {
        "device_provider": health.provider,
        "device_data_status": status,
        "device_synced_at": now,
        "device_missing_fields_json": sorted(set(health.missing_fields)),
        "device_limitations_json": sorted(set(health.limitations)),
    }
    for field, incoming in metadata.items():
        setattr(record, field, incoming)

    has_manual = any(
        getattr(record, field) is not None
        for field in (
            "sleep_quality", "subjective_fatigue", "muscle_soreness", "stress_level",
            "mood_level", "leg_feeling", "pain_level", "pain_location", "illness_symptoms", "notes",
        )
    ) or any(getattr(record, field) == "manual" for field in _FIELD_SOURCES.values())
    record.source = RecoveryCheckinSource.mixed if has_manual else RecoveryCheckinSource.garmin
    return record, changed
