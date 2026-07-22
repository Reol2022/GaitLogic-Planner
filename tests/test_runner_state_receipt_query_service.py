from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from planner_core.enums import RunnerStateSnapshotReceiptStatus
from server.schemas.garmin_sync import ExternalSyncJobRead
from server.services.runner_state_auto_snapshot_service import (
    build_garmin_sync_trigger_reference,
)
from server.services.runner_state_snapshot_receipt_query_service import (
    RunnerStateSnapshotReceiptQueryService,
)


class _Rows:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class _QuerySession:
    def __init__(self, rows=()) -> None:
        self.rows = rows
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return _Rows(self.rows)


def _job(sync_run_id: str, *, job_id: int = 1, provider: str = "garmin") -> ExternalSyncJobRead:
    now = datetime(2026, 7, 22, 9, 30)
    return ExternalSyncJobRead(
        id=job_id,
        sync_run_id=sync_run_id,
        provider=provider,
        sync_mode="recent_7d",
        requested_start=None,
        requested_end=None,
        status="succeeded",
        fetched_count=1,
        created_count=1,
        updated_count=0,
        duplicate_count=0,
        matched_count=1,
        unplanned_count=0,
        needs_review_count=0,
        ignored_count=0,
        failed_count=0,
        is_committed=True,
        committed_at=now,
        created_log_count=1,
        updated_log_count=0,
        unchanged_activity_count=0,
        runner_state_affecting_change_count=1,
        started_at=now,
        finished_at=now,
        error_code=None,
        safe_error_message=None,
        created_at=now,
        updated_at=now,
    )


def test_single_receipt_query_returns_only_public_summary() -> None:
    sync_run_id = str(uuid4())
    db = _QuerySession([
        (
            build_garmin_sync_trigger_reference(sync_run_id),
            RunnerStateSnapshotReceiptStatus.CREATED,
            31,
            None,
        )
    ])

    result = RunnerStateSnapshotReceiptQueryService(db).get_for_sync_run(
        user_id=7,
        sync_run_id=sync_run_id,
    )

    assert result is not None
    assert result.model_dump(mode="json") == {
        "status": "CREATED",
        "snapshot_id": 31,
        "error_code": None,
    }
    statement_text = str(db.statements[0])
    assert "user_id" in statement_text
    assert "trigger_type" in statement_text
    assert "snapshot_payload" not in statement_text


def test_batch_query_is_one_statement_and_retry_jobs_share_result() -> None:
    sync_run_id = str(uuid4())
    db = _QuerySession([
        (
            build_garmin_sync_trigger_reference(sync_run_id),
            RunnerStateSnapshotReceiptStatus.FAILED_NON_BLOCKING,
            None,
            "RUNNER_STATE_CALCULATION_FAILED",
        )
    ])
    service = RunnerStateSnapshotReceiptQueryService(db)

    jobs = service.attach_to_jobs(
        user_id=9,
        jobs=(_job(sync_run_id, job_id=101), _job(sync_run_id, job_id=105)),
    )

    assert len(db.statements) == 1
    assert jobs[0].runner_state_snapshot == jobs[1].runner_state_snapshot
    assert jobs[0].runner_state_snapshot is not None
    assert jobs[0].runner_state_snapshot.status.value == "FAILED_NON_BLOCKING"
    serialized = jobs[0].runner_state_snapshot.model_dump()
    for internal in (
        "receipt_id",
        "user_id",
        "trigger_reference",
        "processing_token",
        "safe_error_message",
        "attempt_count",
        "material_change_count",
    ):
        assert internal not in serialized


def test_empty_and_non_garmin_job_lists_do_not_query() -> None:
    db = _QuerySession()
    service = RunnerStateSnapshotReceiptQueryService(db)

    assert service.get_for_sync_runs(user_id=2, sync_run_ids=()) == {}
    jobs = service.attach_to_jobs(
        user_id=2,
        jobs=(_job(str(uuid4()), provider="mock"),),
    )

    assert jobs[0].runner_state_snapshot is None
    assert db.statements == []


def test_no_receipt_returns_null_and_query_is_scoped_to_current_user() -> None:
    sync_run_id = str(uuid4())
    db = _QuerySession()

    result = RunnerStateSnapshotReceiptQueryService(db).get_for_sync_run(
        user_id=73,
        sync_run_id=sync_run_id,
    )

    assert result is None
    compiled = db.statements[0].compile()
    assert 73 in compiled.params.values()
