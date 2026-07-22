from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from planner_core.enums import RunnerStateAutoSnapshotStatus
from server.common.exceptions import BadRequestError
from server.integrations.activity_sync.outcome import GarminSyncRunOutcome
from server.integrations.activity_sync.pipeline import ActivitySyncPipeline
from server.schemas.runner_state_auto_snapshot import RunnerStateAutoSnapshotResult
from server.services import garmin_sync_service
from server.integrations.activity_sync.workers import sync_worker
from server.workers import external_sync_worker


class _Registry:
    def get(self, provider: str) -> object:
        return SimpleNamespace(provider_key=provider)


class _SyncSession:
    def __init__(self, provider: str = "garmin") -> None:
        self.job = SimpleNamespace(provider=provider)

    def get(self, _model, _job_id: int):
        return self.job


class _SnapshotSession:
    def __init__(self) -> None:
        self.rollback_count = 0
        self.close_count = 0

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


def _outcome(**changes) -> GarminSyncRunOutcome:
    base = GarminSyncRunOutcome(
        job_id=91,
        user_id=17,
        provider="garmin",
        sync_run_id=str(uuid4()),
        claimed=True,
        committed=True,
        final_status="succeeded",
        runner_state_affecting_change_count=1,
    )
    return replace(base, **changes)


def _success_result(outcome: GarminSyncRunOutcome) -> RunnerStateAutoSnapshotResult:
    return RunnerStateAutoSnapshotResult(
        status=RunnerStateAutoSnapshotStatus.CREATED,
        receipt_id=12,
        snapshot_id=34,
        trigger_reference=f"garmin-sync:{outcome.sync_run_id}",
    )


def test_claimed_garmin_job_uses_one_independent_snapshot_session(monkeypatch) -> None:
    outcome = _outcome(final_status="partially_succeeded")
    monkeypatch.setattr(garmin_sync_service, "run_sync_job", lambda _db, _id: outcome)
    snapshot_session = _SnapshotSession()
    session_factory_calls = 0
    service_calls: list[dict[str, object]] = []

    def session_factory():
        nonlocal session_factory_calls
        session_factory_calls += 1
        return snapshot_session

    class AutoService:
        def __init__(self, db) -> None:
            assert db is snapshot_session

        def process_garmin_sync_outcome(self, **kwargs):
            service_calls.append(kwargs)
            return _success_result(outcome)

    pipeline = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=session_factory,
        auto_snapshot_service_factory=AutoService,
    )
    result = pipeline.run_job(_SyncSession(), outcome.job_id)

    assert result.sync_outcome is outcome
    assert result.runner_state_snapshot == _success_result(outcome)
    assert session_factory_calls == 1
    assert service_calls == [{
        "user_id": 17,
        "sync_job_id": 91,
        "sync_run_id": outcome.sync_run_id,
        "committed": True,
        "material_change_count": 1,
    }]
    assert snapshot_session.close_count == 1
    assert snapshot_session.rollback_count == 0


def test_unclaimed_job_does_not_create_snapshot_session(monkeypatch) -> None:
    outcome = _outcome(claimed=False)
    monkeypatch.setattr(garmin_sync_service, "run_sync_job", lambda _db, _id: outcome)
    pipeline = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=lambda: pytest.fail("Session B must not be created"),
    )

    result = pipeline.run_job(_SyncSession(), outcome.job_id)

    assert result.sync_outcome is outcome
    assert result.runner_state_snapshot is None


def test_pipeline_forwards_committed_and_material_change_without_reinterpreting(monkeypatch) -> None:
    outcome = _outcome(
        committed=False,
        final_status="failed",
        runner_state_affecting_change_count=0,
    )
    monkeypatch.setattr(garmin_sync_service, "run_sync_job", lambda _db, _id: outcome)
    snapshot_session = _SnapshotSession()
    received: list[dict[str, object]] = []

    class AutoService:
        def __init__(self, _db) -> None:
            pass

        def process_garmin_sync_outcome(self, **kwargs):
            received.append(kwargs)
            return RunnerStateAutoSnapshotResult(
                status=RunnerStateAutoSnapshotStatus.SKIPPED_NOT_COMMITTED,
                receipt_id=1,
                snapshot_id=None,
                trigger_reference=f"garmin-sync:{outcome.sync_run_id}",
            )

    result = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=lambda: snapshot_session,
        auto_snapshot_service_factory=AutoService,
    ).run_job(_SyncSession(), outcome.job_id)

    assert received[0]["committed"] is False
    assert received[0]["material_change_count"] == 0
    assert result.runner_state_snapshot is not None
    assert result.runner_state_snapshot.status == RunnerStateAutoSnapshotStatus.SKIPPED_NOT_COMMITTED


def test_snapshot_boundary_failure_is_non_blocking_and_closes_session(
    monkeypatch,
    caplog,
) -> None:
    outcome = _outcome()
    provider_calls = 0

    def run_sync(_db, _id):
        nonlocal provider_calls
        provider_calls += 1
        return outcome

    monkeypatch.setattr(garmin_sync_service, "run_sync_job", run_sync)
    snapshot_session = _SnapshotSession()

    class BrokenAutoService:
        def __init__(self, _db) -> None:
            pass

        def process_garmin_sync_outcome(self, **_kwargs):
            raise RuntimeError("fictional private detail")

    result = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=lambda: snapshot_session,
        auto_snapshot_service_factory=BrokenAutoService,
    ).run_job(_SyncSession(), outcome.job_id)

    assert result.sync_outcome is outcome
    assert result.runner_state_snapshot is not None
    assert result.runner_state_snapshot.status == RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING
    assert result.runner_state_snapshot.error_code == "AUTO_SNAPSHOT_PIPELINE_FAILED"
    assert provider_calls == 1
    assert snapshot_session.rollback_count == 1
    assert snapshot_session.close_count == 1
    assert "fictional private detail" not in caplog.text


def test_snapshot_session_factory_failure_is_non_blocking(monkeypatch) -> None:
    outcome = _outcome()
    monkeypatch.setattr(garmin_sync_service, "run_sync_job", lambda _db, _id: outcome)

    def fail_session_factory():
        raise RuntimeError("fictional session failure")

    result = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=fail_session_factory,
    ).run_job(_SyncSession(), outcome.job_id)

    assert result.sync_outcome is outcome
    assert result.runner_state_snapshot is not None
    assert result.runner_state_snapshot.status == RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING


def test_non_garmin_provider_never_creates_snapshot_session() -> None:
    pipeline = ActivitySyncPipeline(
        registry=_Registry(),
        snapshot_session_factory=lambda: pytest.fail("Session B must not be created"),
    )

    with pytest.raises(BadRequestError):
        pipeline.run_job(_SyncSession(provider="mock"), 1)


def test_background_task_and_polling_worker_only_delegate_to_pipeline(monkeypatch) -> None:
    outcome = _outcome()
    result = SimpleNamespace(
        sync_outcome=outcome,
        runner_state_snapshot=_success_result(outcome),
    )
    calls: list[tuple[str, int | None]] = []

    class Context:
        def __enter__(self):
            return "fictional-session-a"

        def __exit__(self, *_args):
            return False

    class Pipeline:
        def run_job(self, db, job_id):
            assert db == "fictional-session-a"
            calls.append(("background", job_id))
            return result

        def run_next_job(self, db):
            assert db == "fictional-session-a"
            calls.append(("worker", None))
            return result

    monkeypatch.setattr(sync_worker, "SessionLocal", Context)
    monkeypatch.setattr(sync_worker, "ActivitySyncPipeline", Pipeline)
    monkeypatch.setattr(external_sync_worker, "SessionLocal", Context)
    monkeypatch.setattr(external_sync_worker, "ActivitySyncPipeline", Pipeline)

    sync_worker.run_sync_job_in_background(91)
    processed = external_sync_worker.process_next_job()

    assert processed is True
    assert calls == [("background", 91), ("worker", None)]
