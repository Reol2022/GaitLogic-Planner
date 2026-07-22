from __future__ import annotations

from datetime import date, datetime, timedelta
import threading
from urllib.parse import quote_plus
from uuid import UUID, uuid4

import pymysql
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from planner_core.config import get_settings
from planner_core.database.models import (
    ExternalAccountConnection,
    ExternalSyncJob,
    RunnerStateSnapshotRecord,
    RunnerStateSnapshotTriggerReceipt,
    UserAccount,
)
from planner_core.enums import (
    RunnerStateAutoSnapshotStatus,
    RunnerStateSnapshotReceiptStatus,
    RunnerStateSnapshotTriggerType,
)
from server.services.runner_state_auto_snapshot_service import (
    RUNNER_STATE_RECEIPT_LEASE,
    RunnerStateAutoSnapshotService,
    build_garmin_sync_trigger_reference,
)
from server.services.runner_state_service import build_runner_state_snapshot
from server.services.runner_state_snapshot_service import RunnerStateSnapshotService
from server.services.weekly_review_stats_service import APP_TIMEZONE


@pytest.fixture(scope="module")
def auto_snapshot_factory():
    settings = get_settings()
    database = f"gaitlogic_test_auto_snapshot_{uuid4().hex[:10]}"
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
    created = False
    engine = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        created = True
        url = (
            f"mysql+pymysql://{quote_plus(settings.mysql_user)}:{quote_plus(settings.mysql_password)}@"
            f"{settings.mysql_host}:{settings.mysql_port}/{database}?charset=utf8mb4"
        )
        engine = create_engine(url, future=True, pool_pre_ping=True)
        UserAccount.__table__.create(engine)
        ExternalAccountConnection.__table__.create(engine)
        ExternalSyncJob.__table__.create(engine)
        RunnerStateSnapshotRecord.__table__.create(engine)
        RunnerStateSnapshotTriggerReceipt.__table__.create(engine)
        factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
        yield factory
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        admin.close()


def _user_job(
    session: Session,
    *,
    sync_run_id: str | None = None,
    user: UserAccount | None = None,
) -> tuple[UserAccount, ExternalSyncJob]:
    marker = uuid4().hex[:10]
    if user is None:
        user = UserAccount(
            username=f"fictional-auto-{marker}",
            password_hash="fictional-hash",
            status="active",
        )
        session.add(user)
        session.flush()
    connection = ExternalAccountConnection(
        user_id=user.id,
        provider="garmin",
        status="connected",
        connector_version="fictional-v1",
        encrypted_token_payload="fictional-encrypted-value",
    )
    session.add(connection)
    session.flush()
    job = ExternalSyncJob(
        user_id=user.id,
        connection_id=connection.id,
        provider="garmin",
        sync_mode="recent_7d",
        status="succeeded",
        sync_run_id=sync_run_id or str(uuid4()),
    )
    session.add(job)
    session.commit()
    return user, job


def _snapshot(user_id: int, *, distance_7d_km: float = 12.5):
    snapshot = build_runner_state_snapshot(
        runner_id=user_id,
        cycle=None,
        log_rows=[],
        planned_workouts=[],
        generated_at=datetime(2026, 7, 20, 18, 30, tzinfo=APP_TIMEZONE),
        timezone_name="Asia/Shanghai",
        calculation_window_end=date(2026, 7, 20),
    )
    snapshot.recent_training.distance_7d_km = distance_7d_km
    snapshot.recent_training.distance_28d_km = 46.75
    return snapshot


class _StateStub:
    def __init__(self, snapshot=None, *, error: Exception | None = None) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls = 0

    def get_current(self, _user: UserAccount):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.snapshot


def _service(session: Session, stub: _StateStub, *, clock=None) -> RunnerStateAutoSnapshotService:
    snapshot_service = RunnerStateSnapshotService(
        session,
        runner_state_service=stub,
        clock=clock or (lambda: datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE)),
    )
    return RunnerStateAutoSnapshotService(
        session,
        snapshot_service=snapshot_service,
        clock=clock or (lambda: datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE)),
    )


def _process(service, user, job, *, committed=True, changes=1):
    return service.process_garmin_sync_outcome(
        user_id=int(user.id),
        sync_job_id=int(job.id),
        sync_run_id=job.sync_run_id,
        committed=committed,
        material_change_count=changes,
    )


def test_trigger_reference_is_stable_and_rejects_noncanonical_values() -> None:
    run_id = str(uuid4())
    assert build_garmin_sync_trigger_reference(run_id) == f"garmin-sync:{run_id}"
    UUID(run_id)
    for invalid in ("", "  ", "job-12", run_id.upper(), f" {run_id}"):
        with pytest.raises(ValueError):
            build_garmin_sync_trigger_reference(invalid)


@pytest.mark.parametrize(
    ("committed", "changes", "expected"),
    (
        (False, 2, RunnerStateAutoSnapshotStatus.SKIPPED_NOT_COMMITTED),
        (True, 0, RunnerStateAutoSnapshotStatus.SKIPPED_NO_MATERIAL_CHANGE),
    ),
)
def test_skips_do_not_calculate_or_create_snapshot(
    auto_snapshot_factory, committed, changes, expected
) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        stub = _StateStub(_snapshot(user.id))
        result = _process(_service(session, stub), user, job, committed=committed, changes=changes)
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, result.receipt_id)
        assert result.status == expected
        assert result.snapshot_id is None
        assert stub.calls == 0
        assert session.scalar(select(func.count()).select_from(RunnerStateSnapshotRecord)) == 0
        assert receipt is not None
        assert receipt.status.value == expected.value
        assert receipt.processing_token is None
        assert receipt.completed_at is not None


def test_negative_material_change_is_rejected_before_writing(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        with pytest.raises(ValueError):
            _process(_service(session, _StateStub(_snapshot(user.id))), user, job, changes=-1)
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotTriggerReceipt).where(
                RunnerStateSnapshotTriggerReceipt.user_id == user.id
            )
        ) == 0


def test_material_change_creates_garmin_snapshot_and_receipt(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        result = _process(_service(session, _StateStub(_snapshot(user.id))), user, job)
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, result.receipt_id)
        snapshot = session.get(RunnerStateSnapshotRecord, result.snapshot_id)
        assert result.status == RunnerStateAutoSnapshotStatus.CREATED
        assert receipt.status == RunnerStateSnapshotReceiptStatus.CREATED
        assert receipt.snapshot_id == snapshot.id
        assert snapshot.trigger_type == RunnerStateSnapshotTriggerType.GARMIN_SYNC
        assert snapshot.trigger_reference == f"garmin-sync:{job.sync_run_id}"


def test_same_trigger_replay_does_not_recalculate(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        first_stub = _StateStub(_snapshot(user.id))
        first = _process(_service(session, first_stub), user, job)
        replay_stub = _StateStub(_snapshot(user.id, distance_7d_km=99))
        replay = _process(_service(session, replay_stub), user, job)
        assert replay.status == RunnerStateAutoSnapshotStatus.ALREADY_PROCESSED_TRIGGER
        assert replay.receipt_id == first.receipt_id
        assert replay.snapshot_id == first.snapshot_id
        assert replay_stub.calls == 0
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotTriggerReceipt).where(
                RunnerStateSnapshotTriggerReceipt.user_id == user.id
            )
        ) == 1


def test_different_trigger_with_same_payload_points_to_existing_manual_snapshot(
    auto_snapshot_factory,
) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        snapshot = _snapshot(user.id)
        manual = RunnerStateSnapshotService(
            session,
            runner_state_service=_StateStub(snapshot),
            clock=lambda: datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE),
        ).save_current(user)
        result = _process(_service(session, _StateStub(snapshot)), user, job)
        persisted = session.get(RunnerStateSnapshotRecord, manual.snapshot.id)
        assert result.status == RunnerStateAutoSnapshotStatus.DUPLICATE_PAYLOAD
        assert result.snapshot_id == manual.snapshot.id
        assert persisted.trigger_type == RunnerStateSnapshotTriggerType.MANUAL
        assert persisted.trigger_reference is None
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotRecord).where(
                RunnerStateSnapshotRecord.user_id == user.id
            )
        ) == 1


def test_skipped_receipt_can_be_reopened_by_retry_job(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, first_job = _user_job(session)
        run_id = first_job.sync_run_id
        first = _process(
            _service(session, _StateStub(_snapshot(user.id))),
            user,
            first_job,
            committed=False,
            changes=0,
        )
        _same_user, retry_job = _user_job(session, sync_run_id=run_id, user=user)
        retried = _process(
            _service(session, _StateStub(_snapshot(user.id))), user, retry_job, changes=1
        )
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, first.receipt_id)
        session.refresh(receipt)
        assert retried.status == RunnerStateAutoSnapshotStatus.CREATED
        assert retried.receipt_id == first.receipt_id
        assert receipt.attempt_count == 2
        assert receipt.sync_job_id == retry_job.id


def test_unexpired_processing_is_not_reclaimed(auto_snapshot_factory) -> None:
    now = datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE)
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        receipt = RunnerStateSnapshotTriggerReceipt(
            user_id=user.id,
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=f"garmin-sync:{job.sync_run_id}",
            status=RunnerStateSnapshotReceiptStatus.PROCESSING,
            sync_job_id=job.id,
            material_change_count=1,
            is_committed=True,
            attempt_count=1,
            processing_token=str(uuid4()),
            locked_at=now.replace(tzinfo=None) - RUNNER_STATE_RECEIPT_LEASE + timedelta(seconds=1),
        )
        session.add(receipt)
        session.commit()
        stub = _StateStub(_snapshot(user.id))
        result = _process(_service(session, stub, clock=lambda: now), user, job)
        assert result.status == RunnerStateAutoSnapshotStatus.PROCESSING_BY_ANOTHER_WORKER
        assert stub.calls == 0
        assert receipt.attempt_count == 1


def test_expired_processing_is_reclaimed_with_new_token(auto_snapshot_factory) -> None:
    now = datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE)
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        old_token = str(uuid4())
        receipt = RunnerStateSnapshotTriggerReceipt(
            user_id=user.id,
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=f"garmin-sync:{job.sync_run_id}",
            status=RunnerStateSnapshotReceiptStatus.PROCESSING,
            sync_job_id=job.id,
            material_change_count=1,
            is_committed=True,
            attempt_count=1,
            processing_token=old_token,
            locked_at=now.replace(tzinfo=None) - RUNNER_STATE_RECEIPT_LEASE - timedelta(seconds=1),
        )
        session.add(receipt)
        session.commit()
        result = _process(_service(session, _StateStub(_snapshot(user.id)), clock=lambda: now), user, job)
        session.refresh(receipt)
        assert result.status == RunnerStateAutoSnapshotStatus.CREATED
        assert receipt.attempt_count == 2
        assert receipt.processing_token is None
        service = _service(session, _StateStub(_snapshot(user.id)), clock=lambda: now)
        assert service._complete_receipt_if_owned(
            receipt_id=receipt.id,
            processing_token=old_token,
            status=RunnerStateSnapshotReceiptStatus.DUPLICATE_PAYLOAD,
            snapshot_id=result.snapshot_id,
        ) is False
        session.rollback()


def test_runner_state_failure_is_nonblocking_and_reopenable(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, first_job = _user_job(session)
        failed = _process(
            _service(session, _StateStub(error=RuntimeError("fictional calculation failure"))),
            user,
            first_job,
        )
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, failed.receipt_id)
        assert failed.status == RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING
        assert failed.error_code == "RUNNER_STATE_CALCULATION_FAILED"
        assert receipt.status == RunnerStateSnapshotReceiptStatus.FAILED_NON_BLOCKING
        assert receipt.snapshot_id is None
        assert session.get(ExternalSyncJob, first_job.id).status == "succeeded"
        _same_user, retry_job = _user_job(session, sync_run_id=first_job.sync_run_id, user=user)
        retried = _process(_service(session, _StateStub(_snapshot(user.id))), user, retry_job)
        assert retried.status == RunnerStateAutoSnapshotStatus.CREATED


def test_concurrent_same_trigger_has_one_owner_and_one_receipt(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as setup:
        user, job = _user_job(setup)
        user_id, job_id, run_id = int(user.id), int(job.id), job.sync_run_id

    entered = threading.Event()
    release = threading.Event()
    outcomes = []
    errors: list[BaseException] = []

    class BlockingStub(_StateStub):
        def get_current(self, user):
            entered.set()
            assert release.wait(10)
            return super().get_current(user)

    def first_worker() -> None:
        try:
            with auto_snapshot_factory() as session:
                outcomes.append(
                    RunnerStateAutoSnapshotService(
                        session,
                        snapshot_service=RunnerStateSnapshotService(
                            session, runner_state_service=BlockingStub(_snapshot(user_id))
                        ),
                    ).process_garmin_sync_outcome(
                        user_id=user_id,
                        sync_job_id=job_id,
                        sync_run_id=run_id,
                        committed=True,
                        material_change_count=1,
                    )
                )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=first_worker)
    thread.start()
    assert entered.wait(10)
    with auto_snapshot_factory() as session:
        second = RunnerStateAutoSnapshotService(session).process_garmin_sync_outcome(
            user_id=user_id,
            sync_job_id=job_id,
            sync_run_id=run_id,
            committed=True,
            material_change_count=1,
        )
    release.set()
    thread.join(10)
    assert errors == []
    assert second.status == RunnerStateAutoSnapshotStatus.PROCESSING_BY_ANOTHER_WORKER
    assert outcomes[0].status == RunnerStateAutoSnapshotStatus.CREATED
    with auto_snapshot_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotTriggerReceipt).where(
                RunnerStateSnapshotTriggerReceipt.trigger_reference == f"garmin-sync:{run_id}"
            )
        ) == 1


def test_same_trigger_reference_is_scoped_by_user(auto_snapshot_factory) -> None:
    shared_run_id = str(uuid4())
    with auto_snapshot_factory() as session:
        first_user, first_job = _user_job(session, sync_run_id=shared_run_id)
        second_user, second_job = _user_job(session, sync_run_id=shared_run_id)
        first = _process(
            _service(session, _StateStub(_snapshot(first_user.id))),
            first_user,
            first_job,
            changes=0,
        )
        second = _process(
            _service(session, _StateStub(_snapshot(second_user.id))),
            second_user,
            second_job,
            changes=0,
        )
        assert first.receipt_id != second.receipt_id
        assert first.status == second.status == (
            RunnerStateAutoSnapshotStatus.SKIPPED_NO_MATERIAL_CHANGE
        )


def test_database_unique_constraint_rejects_duplicate_receipt(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        values = dict(
            user_id=user.id,
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=f"garmin-sync:{job.sync_run_id}",
            status=RunnerStateSnapshotReceiptStatus.PROCESSING,
            sync_job_id=job.id,
            material_change_count=0,
            is_committed=True,
            attempt_count=1,
            processing_token=str(uuid4()),
            locked_at=datetime(2026, 7, 20, 19),
        )
        session.add(RunnerStateSnapshotTriggerReceipt(**values))
        session.commit()
        session.add(RunnerStateSnapshotTriggerReceipt(**values))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_foreign_key_delete_actions_preserve_receipt_audit(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        created = _process(_service(session, _StateStub(_snapshot(user.id))), user, job)
        receipt_id = created.receipt_id
        snapshot = session.get(RunnerStateSnapshotRecord, created.snapshot_id)
        session.execute(text("DELETE FROM external_sync_job WHERE id = :id"), {"id": job.id})
        session.commit()
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, receipt_id)
        assert receipt.sync_job_id is None
        session.execute(
            text("DELETE FROM runner_state_snapshots WHERE id = :id"), {"id": snapshot.id}
        )
        session.commit()
        session.refresh(receipt)
        assert receipt.snapshot_id is None
        session.execute(text("DELETE FROM user_account WHERE id = :id"), {"id": user.id})
        session.commit()
        session.expire_all()
        assert session.get(RunnerStateSnapshotTriggerReceipt, receipt_id) is None


@pytest.mark.parametrize(
    ("failure_stage", "expected_code"),
    (
        ("serialization", "SNAPSHOT_SERIALIZATION_FAILED"),
        ("persistence", "SNAPSHOT_PERSIST_FAILED"),
        ("completion", "RECEIPT_COMPLETION_FAILED"),
    ),
)
def test_phase_b_failures_are_recorded_and_snapshot_is_rolled_back(
    auto_snapshot_factory, monkeypatch, failure_stage, expected_code
) -> None:
    with auto_snapshot_factory() as session:
        user, job = _user_job(session)
        service = _service(session, _StateStub(_snapshot(user.id)))
        if failure_stage == "serialization":
            monkeypatch.setattr(
                "server.services.runner_state_auto_snapshot_service.serialize_runner_state_snapshot",
                lambda _snapshot: (_ for _ in ()).throw(TypeError("fictional serializer failure")),
            )
        elif failure_stage == "persistence":
            monkeypatch.setattr(
                service.snapshot_service,
                "create_or_get_snapshot_in_transaction",
                lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("fictional insert failure")),
            )
        else:
            monkeypatch.setattr(
                service,
                "_complete_receipt_if_owned",
                lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("fictional completion failure")),
            )
        result = _process(service, user, job)
        receipt = session.get(RunnerStateSnapshotTriggerReceipt, result.receipt_id)
        assert result.status == RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING
        assert result.error_code == expected_code
        assert receipt.status == RunnerStateSnapshotReceiptStatus.FAILED_NON_BLOCKING
        assert receipt.snapshot_id is None
        assert receipt.processing_token is None
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotRecord).where(
                RunnerStateSnapshotRecord.user_id == user.id
            )
        ) == 0
        assert session.get(ExternalSyncJob, job.id).status == "succeeded"


def test_transactional_snapshot_creation_does_not_commit(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as writer:
        user, _job = _user_job(writer)
        service = RunnerStateSnapshotService(
            writer,
            runner_state_service=_StateStub(_snapshot(user.id)),
            clock=lambda: datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE),
        )
        result = service.create_or_get_snapshot_in_transaction(
            user_id=user.id,
            snapshot=_snapshot(user.id),
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=f"garmin-sync:{uuid4()}",
        )
        assert result.created is True
        with auto_snapshot_factory() as observer:
            assert observer.get(RunnerStateSnapshotRecord, result.snapshot.id) is None
        writer.rollback()
        assert writer.get(RunnerStateSnapshotRecord, result.snapshot.id) is None


def test_sync_job_reference_cannot_cross_users(auto_snapshot_factory) -> None:
    with auto_snapshot_factory() as session:
        owner, job = _user_job(session)
        other, _other_job = _user_job(session)
        result = RunnerStateAutoSnapshotService(session).process_garmin_sync_outcome(
            user_id=other.id,
            sync_job_id=job.id,
            sync_run_id=job.sync_run_id,
            committed=True,
            material_change_count=1,
        )
        assert result.status == RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING
        assert result.receipt_id is None
        assert result.error_code == "AUTO_SNAPSHOT_TRANSACTION_FAILED"
        assert session.scalar(
            select(func.count()).select_from(RunnerStateSnapshotTriggerReceipt).where(
                RunnerStateSnapshotTriggerReceipt.user_id == other.id
            )
        ) == 0


def test_concurrent_expired_lease_recovery_has_one_new_owner(auto_snapshot_factory) -> None:
    now = datetime(2026, 7, 20, 19, tzinfo=APP_TIMEZONE)
    with auto_snapshot_factory() as setup:
        user, job = _user_job(setup)
        receipt = RunnerStateSnapshotTriggerReceipt(
            user_id=user.id,
            trigger_type=RunnerStateSnapshotTriggerType.GARMIN_SYNC,
            trigger_reference=f"garmin-sync:{job.sync_run_id}",
            status=RunnerStateSnapshotReceiptStatus.PROCESSING,
            sync_job_id=job.id,
            material_change_count=1,
            is_committed=True,
            attempt_count=1,
            processing_token=str(uuid4()),
            locked_at=now.replace(tzinfo=None) - RUNNER_STATE_RECEIPT_LEASE - timedelta(seconds=1),
        )
        setup.add(receipt)
        setup.commit()
        user_id, job_id, run_id, receipt_id = user.id, job.id, job.sync_run_id, receipt.id

    entered = threading.Event()
    release = threading.Event()
    outcomes = []

    class BlockingStub(_StateStub):
        def get_current(self, user):
            entered.set()
            assert release.wait(10)
            return super().get_current(user)

    def recovery_worker() -> None:
        with auto_snapshot_factory() as session:
            outcomes.append(
                RunnerStateAutoSnapshotService(
                    session,
                    snapshot_service=RunnerStateSnapshotService(
                        session, runner_state_service=BlockingStub(_snapshot(user_id))
                    ),
                    clock=lambda: now,
                ).process_garmin_sync_outcome(
                    user_id=user_id,
                    sync_job_id=job_id,
                    sync_run_id=run_id,
                    committed=True,
                    material_change_count=1,
                )
            )

    thread = threading.Thread(target=recovery_worker)
    thread.start()
    assert entered.wait(10)
    with auto_snapshot_factory() as session:
        other = RunnerStateAutoSnapshotService(session, clock=lambda: now).process_garmin_sync_outcome(
            user_id=user_id,
            sync_job_id=job_id,
            sync_run_id=run_id,
            committed=True,
            material_change_count=1,
        )
    release.set()
    thread.join(10)
    assert other.status == RunnerStateAutoSnapshotStatus.PROCESSING_BY_ANOTHER_WORKER
    assert outcomes[0].status == RunnerStateAutoSnapshotStatus.CREATED
    with auto_snapshot_factory() as session:
        persisted = session.get(RunnerStateSnapshotTriggerReceipt, receipt_id)
        assert persisted.attempt_count == 2
