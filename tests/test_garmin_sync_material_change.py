from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus
from uuid import UUID, uuid4
import threading

import pymysql
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from planner_core.config import get_settings
from planner_core.database.base import Base
from planner_core.database.models import ExternalAccountConnection, ExternalSyncJob, UserAccount, WorkoutLog
from planner_core.enums import PainScaleVersion, WorkoutStatusNormalized
from scripts.upgrade_v0103_garmin_sync_material_change import downgrade, upgrade
from server.integrations.activity_sync.outcome import (
    GarminSyncRunOutcome,
    RunnerStateRelevantWorkoutLogProjection,
    WorkoutLogMaterialChangeTracker,
)
from server.schemas.garmin_sync import GarminSyncRequest
from server.services import garmin_sync_service


@pytest.fixture(scope="module")
def mysql_factory():
    settings = get_settings()
    database = f"gaitlogic_test_garmin_material_{uuid4().hex[:10]}"
    try:
        admin = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"isolated MySQL is unavailable: {exc.__class__.__name__}")
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    except pymysql.MySQLError as exc:
        admin.close()
        pytest.skip(f"isolated MySQL database creation is unavailable: {exc.__class__.__name__}")
    admin.close()
    url = (
        f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
        f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
    )
    engine = create_engine(url, future=True, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()
        cleanup = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        with cleanup.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        cleanup.close()


def _user_connection_job(
    session: Session,
    *,
    status: str = "queued",
    suffix: str | None = None,
) -> tuple[UserAccount, ExternalAccountConnection, ExternalSyncJob]:
    marker = suffix or uuid4().hex[:10]
    user = UserAccount(
        username=f"fictional-garmin-{marker}",
        password_hash="fictional-password-hash",
        status="active",
    )
    session.add(user)
    session.flush()
    connection = ExternalAccountConnection(
        user_id=user.id,
        provider="garmin",
        status="connected",
        connector_version="mock-contract-v1",
        encrypted_token_payload="fictional-encrypted-token",
    )
    session.add(connection)
    session.flush()
    job = ExternalSyncJob(
        user_id=user.id,
        connection_id=connection.id,
        provider="garmin",
        sync_mode="recent_7d",
        requested_start=datetime(2026, 7, 1),
        requested_end=datetime(2026, 7, 8),
        status=status,
        sync_run_id=str(uuid4()),
    )
    session.add(job)
    session.commit()
    return user, connection, job


def _log(user_id: int, log_id: int = 501) -> WorkoutLog:
    log = WorkoutLog(
        user_id=user_id,
        status_raw="completed",
        status_normalized=WorkoutStatusNormalized.completed_normal,
        pain_scale_version=PainScaleVersion.native_0_10,
        activity_date=date(2026, 7, 8),
        session_index=1,
        sport_type="running",
        workout_type="easy",
        is_unplanned=True,
        source_type="garmin_sync",
        subjective_status="pending",
        cycle_assignment_status="unassigned",
    )
    log.id = log_id
    return log


def test_projection_normalizes_equivalent_numeric_and_enum_values() -> None:
    first = _log(1)
    first.actual_distance_km = Decimal("10.5000")
    second = _log(1)
    second.actual_distance_km = 10.5
    assert RunnerStateRelevantWorkoutLogProjection.from_workout_log(first) == (
        RunnerStateRelevantWorkoutLogProjection.from_workout_log(second)
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("planned_workout_id", 42),
        ("activity_date", date(2026, 7, 9)),
        ("status_normalized", WorkoutStatusNormalized.completed_adjusted),
        ("workout_type", "threshold"),
        ("actual_distance_km", Decimal("12.5")),
        ("actual_duration_seconds", 3600),
        ("rpe", 7),
        ("avg_heart_rate", 151),
        ("max_heart_rate", 176),
    ),
)
def test_each_runner_state_relevant_field_is_material(field: str, value: object) -> None:
    log = _log(1)
    tracker = WorkoutLogMaterialChangeTracker()
    tracker.capture_before(log)
    setattr(log, field, value)
    assert tracker.counts().updated_log_count == 1


def test_irrelevant_metrics_and_payload_metadata_are_not_material() -> None:
    log = _log(1)
    tracker = WorkoutLogMaterialChangeTracker()
    tracker.capture_before(log)
    log.average_cadence_spm = 182
    log.avg_pace_seconds_per_km = 295
    log.elevation_gain_m = 90
    log.field_sources_json = {"payload_hash": "fictional"}
    assert tracker.counts().runner_state_affecting_change_count == 0


def test_null_and_real_zero_are_distinct_and_composite_log_counts_once() -> None:
    log = _log(1)
    first = WorkoutLogMaterialChangeTracker()
    first.capture_before(log)
    log.actual_distance_km = Decimal("0")
    second = WorkoutLogMaterialChangeTracker()
    second.capture_before(log)
    log.actual_duration_seconds = 0
    first.merge(second)
    counts = first.counts()
    assert counts.updated_log_count == 1
    assert counts.runner_state_affecting_change_count == 1


def test_created_log_counts_once() -> None:
    log = _log(1)
    tracker = WorkoutLogMaterialChangeTracker()
    tracker.capture_created(log)
    log.actual_distance_km = Decimal("8.0")
    assert tracker.counts().created_log_count == 1
    assert tracker.counts().updated_log_count == 0


def test_server_generates_sync_run_id_and_retry_inherits_it(mysql_factory) -> None:
    with mysql_factory() as session:
        user, _connection, original = _user_connection_job(session, status="failed")
        original.failed_count = 2
        session.commit()
        retried = garmin_sync_service.retry_sync_job(session, user.id, original.id)
        assert retried.id != original.id
        assert retried.sync_run_id == original.sync_run_id
        assert retried.status == "queued"
        assert retried.created_log_count == 0
        assert retried.runner_state_affecting_change_count == 0


def test_client_sync_payload_cannot_supply_internal_sync_run_id(mysql_factory) -> None:
    payload = GarminSyncRequest.model_validate(
        {"sync_mode": "recent_7d", "sync_run_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert "sync_run_id" not in payload.model_dump()
    with mysql_factory() as session:
        user, _connection, original = _user_connection_job(session, status="failed")
        original.status = "succeeded"
        session.commit()
        created = garmin_sync_service.enqueue_sync_job(session, user.id, payload)
        assert created.sync_run_id != "00000000-0000-0000-0000-000000000000"
        UUID(created.sync_run_id)


def test_atomic_claim_allows_only_one_background_or_worker_claimant(mysql_factory) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)
        job_id = int(job.id)

    barrier = threading.Barrier(2)
    results: list[bool] = []
    errors: list[BaseException] = []

    def claim() -> None:
        try:
            with mysql_factory() as session:
                barrier.wait(timeout=5)
                results.append(garmin_sync_service.claim_sync_job(session, job_id))
        except BaseException as exc:  # captured for the asserting test thread
            errors.append(exc)

    threads = [threading.Thread(target=claim), threading.Thread(target=claim)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert sorted(results) == [False, True]
    with mysql_factory() as session:
        persisted = session.get(ExternalSyncJob, job_id)
        assert persisted is not None
        assert persisted.status == "running"
        assert persisted.attempt_count == 1


class _FakeProvider:
    connector_version = "mock-contract-v1"

    def __init__(self, activities: list[SimpleNamespace], *, fail_refresh: bool = False) -> None:
        self.activities = activities
        self.fail_refresh = fail_refresh

    def restore_session(self, _token: dict) -> None:
        return None

    def fetch_activities(self, _start: datetime, _end: datetime) -> list[SimpleNamespace]:
        return self.activities

    def refresh_session(self):
        if self.fail_refresh:
            raise RuntimeError("fictional fatal refresh failure")
        return None


def _activities(count: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            external_activity_id=f"fictional-activity-{index}",
            start_time_local=datetime(2026, 7, 8, 6) + timedelta(hours=index),
        )
        for index in range(count)
    ]


def _install_fake_sync(monkeypatch, provider: _FakeProvider, process) -> None:
    monkeypatch.setattr(garmin_sync_service, "decrypt_token_payload", lambda _value: {"fictional": True})
    monkeypatch.setattr(garmin_sync_service, "_provider_for_connection", lambda _connection: provider)
    monkeypatch.setattr(garmin_sync_service, "_process_provider_activity", process)


def _successful_process(session: Session, job: ExternalSyncJob, activity, _version: str, **kwargs) -> str:
    tracker = kwargs["material_tracker"]
    log = _log(job.user_id, log_id=9000 + int(activity.external_activity_id.rsplit("-", 1)[1]))
    log.id = None
    log.external_activity_id = activity.external_activity_id
    session.add(log)
    session.flush()
    tracker.capture_created(log)
    return "created"


def test_no_activity_sync_commits_with_zero_material_change(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)
        _install_fake_sync(monkeypatch, _FakeProvider([]), _successful_process)
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome == GarminSyncRunOutcome(
            job_id=job.id,
            sync_run_id=job.sync_run_id,
            claimed=True,
            committed=True,
            final_status="succeeded",
        )


def test_partial_success_commits_successful_activity_only(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)

        def process(db, current_job, activity, version, **kwargs):
            if activity.external_activity_id.endswith("1"):
                raise ValueError("fictional activity failure")
            return _successful_process(db, current_job, activity, version, **kwargs)

        _install_fake_sync(monkeypatch, _FakeProvider(_activities(2)), process)
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome.final_status == "partially_succeeded"
        assert outcome.committed is True
        assert outcome.created_log_count == 1
        assert outcome.runner_state_affecting_change_count == 1
        assert session.scalar(select(WorkoutLog).where(WorkoutLog.user_id == job.user_id)) is not None


def test_all_activity_failures_rollback_training_data(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)

        def process(db, current_job, activity, version, **kwargs):
            _successful_process(db, current_job, activity, version, **kwargs)
            raise ValueError("fictional activity failure after flush")

        _install_fake_sync(monkeypatch, _FakeProvider(_activities(2)), process)
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome.final_status == "failed"
        assert outcome.committed is False
        assert outcome.created_log_count == 0
        assert session.scalar(select(WorkoutLog).where(WorkoutLog.user_id == job.user_id)) is None


def test_outer_fatal_error_rolls_back_successful_savepoint(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)
        _install_fake_sync(
            monkeypatch,
            _FakeProvider(_activities(1), fail_refresh=True),
            _successful_process,
        )
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome.final_status == "failed"
        assert outcome.committed is False
        assert session.scalar(select(WorkoutLog).where(WorkoutLog.user_id == job.user_id)) is None


def test_final_commit_failure_rolls_back_then_marks_job_failed(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session)
        _install_fake_sync(monkeypatch, _FakeProvider(_activities(1)), _successful_process)
        real_commit = session.commit
        commit_calls = 0

        def fail_final_commit_once() -> None:
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls == 2:
                raise RuntimeError("fictional database commit failure")
            real_commit()

        monkeypatch.setattr(session, "commit", fail_final_commit_once)
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome.final_status == "failed"
        assert outcome.committed is False
        assert outcome.warning_codes == ("SYNC_COMMIT_FAILED",)
        assert session.scalar(select(WorkoutLog).where(WorkoutLog.user_id == job.user_id)) is None


def test_running_job_returns_not_claimed_without_calling_provider(mysql_factory, monkeypatch) -> None:
    with mysql_factory() as session:
        _user, _connection, job = _user_connection_job(session, status="running")
        monkeypatch.setattr(
            garmin_sync_service,
            "_provider_for_connection",
            lambda _connection: pytest.fail("provider must not be called by an unclaimed runner"),
        )
        outcome = garmin_sync_service.run_sync_job(session, job.id)
        assert outcome.claimed is False
        assert outcome.warning_codes == ("JOB_NOT_CLAIMED",)


def test_mysql_upgrade_backfills_uuid_and_round_trips() -> None:
    settings = get_settings()
    database = f"gaitlogic_test_garmin_migration_{uuid4().hex[:10]}"
    try:
        admin = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        pytest.skip(f"isolated MySQL is unavailable: {exc.__class__.__name__}")
    database_created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        database_created = True
        url = (
            f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
            f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
        )
        engine = create_engine(url, future=True)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE `external_sync_job` (
                      `id` BIGINT NOT NULL AUTO_INCREMENT,
                      `idempotency_key` VARCHAR(128) NULL,
                      `failed_count` INT NOT NULL DEFAULT 0,
                      PRIMARY KEY (`id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
            connection.execute(
                text("INSERT INTO `external_sync_job` (`idempotency_key`) VALUES ('fictional-a'), ('fictional-b')")
            )
            upgrade(connection)
            columns = {column["name"]: column for column in inspect(connection).get_columns("external_sync_job")}
            indexes = {index["name"] for index in inspect(connection).get_indexes("external_sync_job")}
            assert columns["sync_run_id"]["nullable"] is False
            assert "ix_external_sync_job_sync_run_id" in indexes
            run_ids = list(connection.execute(text("SELECT `sync_run_id` FROM `external_sync_job` ORDER BY `id`")).scalars())
            assert len(set(run_ids)) == 2
            assert all(str(UUID(value)) == value for value in run_ids)
            downgrade(connection)
            assert "sync_run_id" not in {item["name"] for item in inspect(connection).get_columns("external_sync_job")}
            upgrade(connection)
        engine.dispose()
    except pymysql.MySQLError as exc:
        if not database_created:
            pytest.skip(f"isolated MySQL database creation is unavailable: {exc.__class__.__name__}")
        raise
    finally:
        if database_created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        admin.close()


def test_migration_sql_remains_mysql_57_compatible() -> None:
    source = Path("scripts/upgrade_v0103_garmin_sync_material_change.py").read_text(encoding="utf-8")
    assert "UUID()" not in source
    assert "DROP CHECK" not in source
    assert "ADD COLUMN IF NOT EXISTS" not in source
