from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.api.routes import data_sync, garmin_sync
from server.main import app
from server.schemas.garmin_sync import (
    ExternalSyncJobRead,
    RunnerStateSnapshotSyncResultRead,
)


def _job(
    *,
    snapshot: RunnerStateSnapshotSyncResultRead | None,
    status: str = "succeeded",
) -> ExternalSyncJobRead:
    now = datetime(2026, 7, 22, 11, 0)
    return ExternalSyncJobRead(
        id=44,
        sync_run_id=str(uuid4()),
        provider="garmin",
        sync_mode="recent_7d",
        requested_start=None,
        requested_end=None,
        status=status,
        fetched_count=1,
        created_count=1,
        updated_count=0,
        duplicate_count=0,
        matched_count=1,
        unplanned_count=0,
        needs_review_count=0,
        ignored_count=0,
        failed_count=0,
        is_committed=status == "succeeded",
        committed_at=now if status == "succeeded" else None,
        created_log_count=1 if status == "succeeded" else 0,
        updated_log_count=0,
        unchanged_activity_count=0,
        runner_state_affecting_change_count=1 if status == "succeeded" else 0,
        started_at=now,
        finished_at=now if status == "succeeded" else None,
        error_code=None,
        safe_error_message=None,
        created_at=now,
        updated_at=now,
        runner_state_snapshot=snapshot,
    )


class _Facade:
    def __init__(self, row: ExternalSyncJobRead) -> None:
        self.row = row

    def get_sync_job(self, _job_id: int) -> ExternalSyncJobRead:
        return self.row

    def list_sync_jobs(self, **_kwargs) -> list[ExternalSyncJobRead]:
        return [self.row]

    def create_sync_job(self, *_args, **_kwargs) -> ExternalSyncJobRead:
        return self.row


def _with_overrides(monkeypatch, row: ExternalSyncJobRead) -> TestClient:
    current_user = UserAccount(
        id=81,
        username="fictional-api-runner",
        password_hash="fictional-hash",
        status="active",
    )
    facade = _Facade(row)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: object()
    monkeypatch.setattr(garmin_sync, "assert_garmin_sync_available", lambda *_args: None)
    monkeypatch.setattr(data_sync, "assert_data_sync_available", lambda *_args: None)
    monkeypatch.setattr(garmin_sync, "_facade", lambda *_args: facade)
    monkeypatch.setattr(data_sync, "_facade", lambda *_args: facade)
    monkeypatch.setattr(garmin_sync, "run_sync_job_in_background", lambda _job_id: None)
    monkeypatch.setattr(data_sync, "run_sync_job_in_background", lambda _job_id: None)
    return TestClient(app)


def test_garmin_and_data_sync_details_expose_same_safe_nested_result(monkeypatch) -> None:
    row = _job(
        snapshot=RunnerStateSnapshotSyncResultRead(
            status="CREATED",
            snapshot_id=61,
            error_code=None,
        )
    )
    client = _with_overrides(monkeypatch, row)
    try:
        garmin_response = client.get("/api/integrations/garmin/sync-jobs/44")
        generic_response = client.get("/api/data-sync/sync-jobs/44")
    finally:
        app.dependency_overrides.clear()

    assert garmin_response.status_code == 200
    assert generic_response.status_code == 200
    for payload in (garmin_response.json(), generic_response.json()):
        assert payload["runner_state_snapshot"] == {
            "status": "CREATED",
            "snapshot_id": 61,
            "error_code": None,
        }
        serialized = str(payload["runner_state_snapshot"])
        for internal in ("trigger_reference", "processing_token", "safe_error_message"):
            assert internal not in serialized


def test_job_lists_return_processing_and_failed_non_blocking(monkeypatch) -> None:
    for status in ("PROCESSING", "FAILED_NON_BLOCKING"):
        row = _job(
            snapshot=RunnerStateSnapshotSyncResultRead(
                status=status,
                snapshot_id=None,
                error_code="FICTIONAL_SAFE_CODE" if status == "FAILED_NON_BLOCKING" else None,
            )
        )
        client = _with_overrides(monkeypatch, row)
        try:
            garmin_payload = client.get("/api/integrations/garmin/sync-jobs").json()
            generic_payload = client.get("/api/data-sync/sync-jobs").json()["jobs"]
        finally:
            app.dependency_overrides.clear()

        assert garmin_payload[0]["runner_state_snapshot"]["status"] == status
        assert generic_payload[0]["runner_state_snapshot"]["status"] == status


def test_queued_create_has_null_snapshot_result(monkeypatch) -> None:
    client = _with_overrides(monkeypatch, _job(snapshot=None, status="queued"))
    try:
        response = client.post(
            "/api/integrations/garmin/sync",
            json={"sync_mode": "recent_7d"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["runner_state_snapshot"] is None
