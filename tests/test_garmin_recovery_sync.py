from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import BigInteger, DefaultClause, create_engine, select, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from planner_core.database.base import Base
from planner_core.database.models import DailyRecoveryCheckin, ExternalSyncJob, UserAccount
from planner_core.enums import RecoveryCheckinSource
from server.integrations.activity_provider import ProviderError, ProviderRecoverySnapshot
from server.integrations.activity_provider.garmin import GarminActivityProvider
from server.services.garmin_daily_state_sync_service import apply_garmin_daily_health
from server.services.garmin_sync_service import _recovery_sync_range
from server.services.recovery_checkin_service import get_latest_device_checkin
from server.services.recovery_checkin_service import upsert_today_checkin
from server.schemas.recovery_checkin import RecoveryCheckinPayload
from server.services.runner_state_service import build_runner_state_snapshot


@compiles(BigInteger, "sqlite")
def _compile_big_integer_as_integer(_type, _compiler, **_kwargs):
    return "INTEGER"


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    mysql_defaults = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.server_default is not None and "ON UPDATE" in str(column.server_default.arg):
                mysql_defaults.append((column, column.server_default))
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    try:
        Base.metadata.create_all(engine)
    finally:
        for column, default in mysql_defaults:
            column.server_default = default
    session = Session(engine, expire_on_commit=False)
    session.add_all([
        UserAccount(id=7001, username="recovery-fixture", password_hash="x", status="active"),
        UserAccount(id=7002, username="recovery-other", password_hash="x", status="active"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _snapshot(**changes) -> ProviderRecoverySnapshot:
    values = {
        "recovery_date": date(2026, 10, 27),
        "provider": "garmin",
        "sleep_duration_minutes": 455,
        "resting_heart_rate_bpm": 47,
        "hrv_value": Decimal("61.5"),
        "hrv_metric": "last_night_avg",
        "sleep_score": 82,
        "body_battery_end": 74,
    }
    values.update(changes)
    return ProviderRecoverySnapshot(**values)


def test_garmin_health_is_idempotent_and_persists_extended_metrics(db: Session) -> None:
    record, changed = apply_garmin_daily_health(db, user_id=7001, health=_snapshot())
    db.commit()
    assert changed is True
    assert record.sleep_score == 82
    assert record.body_battery_end == 74
    assert record.sleep_source == "garmin"
    assert record.device_data_status == "AVAILABLE"

    _, repeated_changed = apply_garmin_daily_health(db, user_id=7001, health=_snapshot())
    assert repeated_changed is False
    assert db.scalar(select(DailyRecoveryCheckin).where(DailyRecoveryCheckin.user_id == 7001)) is record


def test_manual_objective_field_wins_but_subjective_fields_do_not_freeze_garmin(db: Session) -> None:
    record = DailyRecoveryCheckin(
        user_id=7001,
        checkin_date=date(2026, 10, 27),
        source=RecoveryCheckinSource.manual,
        sleep_duration_minutes=420,
        sleep_source="manual",
        subjective_fatigue=4,
    )
    db.add(record)
    db.commit()

    updated, _ = apply_garmin_daily_health(db, user_id=7001, health=_snapshot())
    assert updated.sleep_duration_minutes == 420
    assert updated.resting_heart_rate_bpm == 47
    assert updated.hrv_value == Decimal("61.5")
    assert updated.subjective_fatigue == 4
    assert updated.source == RecoveryCheckinSource.mixed


def test_missing_device_measurements_are_unavailable_not_zero(db: Session) -> None:
    record, changed = apply_garmin_daily_health(
        db,
        user_id=7001,
        health=_snapshot(
            sleep_duration_minutes=None,
            resting_heart_rate_bpm=None,
            hrv_value=None,
            hrv_metric=None,
            sleep_score=None,
            body_battery_end=None,
            missing_fields=["sleep_duration_minutes", "hrv_value"],
        ),
    )
    assert changed is False
    assert record.device_data_status == "UNAVAILABLE"
    assert record.sleep_duration_minutes is None
    assert record.hrv_value is None


def test_subjective_checkin_does_not_claim_garmin_objective_fields(db: Session, monkeypatch) -> None:
    monkeypatch.setattr("server.services.recovery_checkin_service.local_today", lambda: date(2026, 10, 27))
    record, _ = apply_garmin_daily_health(db, user_id=7001, health=_snapshot())
    db.commit()
    updated = upsert_today_checkin(
        db,
        7001,
        RecoveryCheckinPayload(subjective_fatigue=4, leg_feeling=2),
    )
    assert updated.source == RecoveryCheckinSource.mixed
    assert updated.sleep_source == "garmin"
    assert updated.resting_heart_rate_source == "garmin"
    assert updated.hrv_source == "garmin"


def test_recovery_range_is_independent_of_activity_and_bounded_to_31_days() -> None:
    job = ExternalSyncJob(
        requested_start=datetime(2026, 7, 1),
        requested_end=datetime(2026, 10, 27, 12),
    )
    assert _recovery_sync_range(job, date(2026, 10, 27)) == (
        date(2026, 9, 27),
        date(2026, 10, 27),
    )


def test_runner_state_exposes_recovery_facts_without_changing_inference() -> None:
    recovery = DailyRecoveryCheckin(
        user_id=7001,
        checkin_date=date(2026, 10, 26),
        source=RecoveryCheckinSource.garmin,
        sleep_duration_minutes=455,
        resting_heart_rate_bpm=47,
        hrv_value=Decimal("61.5"),
        hrv_metric="last_night_avg",
        body_battery_end=74,
        device_provider="garmin",
        device_data_status="AVAILABLE",
    )
    snapshot = build_runner_state_snapshot(
        runner_id=7001,
        cycle=None,
        log_rows=[],
        planned_workouts=[],
        generated_at=datetime(2026, 10, 27, 12),
        timezone_name="Asia/Shanghai",
        calculation_window_end=date(2026, 10, 27),
        latest_recovery=recovery,
    )
    assert snapshot.recovery.freshness == "CURRENT"
    assert snapshot.recovery.hrv_value == 61.5
    assert snapshot.fatigue is not None
    assert snapshot.fatigue.state.value == "UNKNOWN"


def test_recovery_network_error_is_not_reported_as_missing_data() -> None:
    class Client:
        def get_sleep_data(self, _day):
            raise TimeoutError("request timed out")

    with pytest.raises(ProviderError) as error:
        GarminActivityProvider()._health_call(Client(), "get_sleep_data", ("2026-10-27",), "sleep", [])
    assert error.value.code == "RECOVERY_NETWORK_ERROR"


def test_latest_device_recovery_is_user_isolated(db: Session, monkeypatch) -> None:
    monkeypatch.setattr("server.services.recovery_checkin_service.local_today", lambda: date(2026, 10, 27))
    db.add_all([
        DailyRecoveryCheckin(
            user_id=7001,
            checkin_date=date(2026, 10, 26),
            source=RecoveryCheckinSource.garmin,
            device_provider="garmin",
            hrv_value=Decimal("60"),
        ),
        DailyRecoveryCheckin(
            user_id=7002,
            checkin_date=date(2026, 10, 27),
            source=RecoveryCheckinSource.garmin,
            device_provider="garmin",
            hrv_value=Decimal("99"),
        ),
    ])
    db.commit()
    result = get_latest_device_checkin(db, 7001)
    assert result is not None
    assert result.user_id == 7001
    assert result.hrv_value == Decimal("60")
