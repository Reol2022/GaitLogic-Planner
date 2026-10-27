from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from planner_core.database.models import DailyRecoveryCheckin
from planner_core.enums import RecoveryCheckinSource
from server.common.exceptions import BadRequestError, NotFoundError
from server.schemas.recovery_checkin import RecoveryCheckinPayload
from server.services.weekly_review_stats_service import local_today

MAX_CHECKIN_RANGE_DAYS = 120


def _assert_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise BadRequestError("end_date must not be earlier than start_date.")
    if (end_date - start_date).days > MAX_CHECKIN_RANGE_DAYS:
        raise BadRequestError("Date range is too large.")


def get_checkin(db: Session, user_id: int, checkin_date: date) -> DailyRecoveryCheckin | None:
    return db.scalar(
        select(DailyRecoveryCheckin).where(
            DailyRecoveryCheckin.user_id == user_id,
            DailyRecoveryCheckin.checkin_date == checkin_date,
        )
    )


def get_today_checkin(db: Session, user_id: int) -> DailyRecoveryCheckin | None:
    return get_checkin(db, user_id, local_today())


def get_latest_device_checkin(
    db: Session, user_id: int, *, max_age_days: int = 2
) -> DailyRecoveryCheckin | None:
    end = local_today()
    start = end - timedelta(days=max_age_days)
    return db.scalar(
        select(DailyRecoveryCheckin)
        .where(
            DailyRecoveryCheckin.user_id == user_id,
            DailyRecoveryCheckin.checkin_date.between(start, end),
            DailyRecoveryCheckin.device_provider.is_not(None),
            or_(
                DailyRecoveryCheckin.sleep_duration_minutes.is_not(None),
                DailyRecoveryCheckin.resting_heart_rate_bpm.is_not(None),
                DailyRecoveryCheckin.hrv_value.is_not(None),
                DailyRecoveryCheckin.body_battery_end.is_not(None),
            ),
        )
        .order_by(DailyRecoveryCheckin.checkin_date.desc())
        .limit(1)
    )


def upsert_today_checkin(
    db: Session, user_id: int, payload: RecoveryCheckinPayload
) -> DailyRecoveryCheckin:
    checkin_date = local_today()
    checkin = get_checkin(db, user_id, checkin_date)
    if checkin is None:
        checkin = DailyRecoveryCheckin(
            user_id=user_id,
            checkin_date=checkin_date,
            source=RecoveryCheckinSource.manual,
        )
        db.add(checkin)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(checkin, key, value)
    for value_field, source_field in {
        "sleep_duration_minutes": "sleep_source",
        "resting_heart_rate_bpm": "resting_heart_rate_source",
        "hrv_value": "hrv_source",
    }.items():
        if value_field in data:
            setattr(checkin, source_field, "manual" if data[value_field] is not None else None)
    if "hrv_metric" in data:
        checkin.hrv_source = "manual" if data["hrv_metric"] is not None else checkin.hrv_source
    checkin.source = (
        RecoveryCheckinSource.mixed
        if checkin.device_provider
        else RecoveryCheckinSource.manual
    )
    db.commit()
    db.refresh(checkin)
    return checkin


def delete_checkin(db: Session, user_id: int, checkin_date: date) -> None:
    checkin = get_checkin(db, user_id, checkin_date)
    if checkin is None:
        raise NotFoundError("Recovery check-in not found.")
    db.delete(checkin)
    db.commit()


def list_checkins(
    db: Session,
    user_id: int,
    start_date: date | None,
    end_date: date | None,
) -> list[DailyRecoveryCheckin]:
    end = end_date or local_today()
    start = start_date or (end - timedelta(days=27))
    _assert_range(start, end)
    return list(
        db.scalars(
            select(DailyRecoveryCheckin)
            .where(
                DailyRecoveryCheckin.user_id == user_id,
                DailyRecoveryCheckin.checkin_date >= start,
                DailyRecoveryCheckin.checkin_date <= end,
            )
            .order_by(DailyRecoveryCheckin.checkin_date)
        )
    )
