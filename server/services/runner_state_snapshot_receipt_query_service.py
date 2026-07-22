from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import RunnerStateSnapshotTriggerReceipt
from planner_core.enums import RunnerStateSnapshotTriggerType
from server.schemas.garmin_sync import (
    ExternalSyncJobRead,
    RunnerStateSnapshotSyncResultRead,
)
from server.services.runner_state_auto_snapshot_service import (
    build_garmin_sync_trigger_reference,
)


class RunnerStateSnapshotReceiptQueryService:
    """Read-only projection of Garmin trigger receipts for sync job responses."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_sync_run(
        self,
        *,
        user_id: int,
        sync_run_id: str,
    ) -> RunnerStateSnapshotSyncResultRead | None:
        return self.get_for_sync_runs(user_id=user_id, sync_run_ids=(sync_run_id,)).get(
            sync_run_id
        )

    def get_for_sync_runs(
        self,
        *,
        user_id: int,
        sync_run_ids: Iterable[str],
    ) -> dict[str, RunnerStateSnapshotSyncResultRead]:
        unique_run_ids = tuple(dict.fromkeys(sync_run_ids))
        if not unique_run_ids:
            return {}

        references_by_run_id = {
            sync_run_id: build_garmin_sync_trigger_reference(sync_run_id)
            for sync_run_id in unique_run_ids
        }
        run_ids_by_reference = {
            trigger_reference: sync_run_id
            for sync_run_id, trigger_reference in references_by_run_id.items()
        }
        rows = self.db.execute(
            select(
                RunnerStateSnapshotTriggerReceipt.trigger_reference,
                RunnerStateSnapshotTriggerReceipt.status,
                RunnerStateSnapshotTriggerReceipt.snapshot_id,
                RunnerStateSnapshotTriggerReceipt.error_code,
            ).where(
                RunnerStateSnapshotTriggerReceipt.user_id == user_id,
                RunnerStateSnapshotTriggerReceipt.trigger_type
                == RunnerStateSnapshotTriggerType.GARMIN_SYNC,
                RunnerStateSnapshotTriggerReceipt.trigger_reference.in_(
                    tuple(run_ids_by_reference)
                ),
            )
        ).all()
        return {
            run_ids_by_reference[trigger_reference]: RunnerStateSnapshotSyncResultRead(
                status=status.value,
                snapshot_id=int(snapshot_id) if snapshot_id is not None else None,
                error_code=error_code,
            )
            for trigger_reference, status, snapshot_id, error_code in rows
        }

    def attach_to_job(
        self,
        *,
        user_id: int,
        job: ExternalSyncJobRead,
    ) -> ExternalSyncJobRead:
        return self.attach_to_jobs(user_id=user_id, jobs=(job,))[0]

    def attach_to_jobs(
        self,
        *,
        user_id: int,
        jobs: Sequence[ExternalSyncJobRead],
    ) -> list[ExternalSyncJobRead]:
        garmin_run_ids = tuple(
            job.sync_run_id for job in jobs if job.provider == "garmin" and job.sync_run_id
        )
        results = self.get_for_sync_runs(
            user_id=user_id,
            sync_run_ids=garmin_run_ids,
        )
        return [
            job.model_copy(
                update={
                    "runner_state_snapshot": results.get(job.sync_run_id)
                    if job.provider == "garmin"
                    else None
                }
            )
            for job in jobs
        ]
