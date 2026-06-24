from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
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
    checkin.source = RecoveryCheckinSource.manual
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
