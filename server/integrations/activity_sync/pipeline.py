from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import ExternalSyncJob
from planner_core.database.session import SessionLocal
from planner_core.enums import RunnerStateAutoSnapshotStatus
from server.common.exceptions import BadRequestError, NotFoundError
from server.integrations.activity_sync.registry import ProviderRegistry, get_provider_registry
from server.integrations.activity_sync.outcome import GarminSyncRunOutcome
from server.schemas.runner_state_auto_snapshot import RunnerStateAutoSnapshotResult
from server.services import garmin_sync_service
from server.services.runner_state_auto_snapshot_service import (
    RunnerStateAutoSnapshotService,
    build_garmin_sync_trigger_reference,
)

logger = logging.getLogger(__name__)

SnapshotSessionFactory = Callable[[], Session]
AutoSnapshotServiceFactory = Callable[[Session], RunnerStateAutoSnapshotService]


@dataclass(frozen=True)
class ActivitySyncPipelineResult:
    sync_outcome: GarminSyncRunOutcome
    runner_state_snapshot: RunnerStateAutoSnapshotResult | None


class ActivitySyncPipeline:
    """Provider-neutral sync job runner.

    v0.9.4 keeps Garmin's mature matching/import implementation in place and
    routes it through this pipeline. Future providers can add their own generic
    processing path behind the same interface.
    """

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        *,
        snapshot_session_factory: SnapshotSessionFactory = SessionLocal,
        auto_snapshot_service_factory: AutoSnapshotServiceFactory = RunnerStateAutoSnapshotService,
    ) -> None:
        self.registry = registry or get_provider_registry()
        self.snapshot_session_factory = snapshot_session_factory
        self.auto_snapshot_service_factory = auto_snapshot_service_factory

    def run_job(self, db: Session, job_id: int) -> ActivitySyncPipelineResult:
        job = db.get(ExternalSyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在。")
        self.registry.get(job.provider)
        if job.provider == "garmin":
            sync_outcome = garmin_sync_service.run_sync_job(db, job_id)
            if not sync_outcome.claimed:
                return ActivitySyncPipelineResult(
                    sync_outcome=sync_outcome,
                    runner_state_snapshot=None,
                )
            return ActivitySyncPipelineResult(
                sync_outcome=sync_outcome,
                runner_state_snapshot=self._process_runner_state_snapshot(sync_outcome),
            )
        raise BadRequestError("该平台暂未接入通用同步流水线。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")

    def run_next_job(self, db: Session) -> ActivitySyncPipelineResult | None:
        job_id = db.scalar(
            select(ExternalSyncJob.id)
            .where(ExternalSyncJob.status == "queued")
            .order_by(ExternalSyncJob.created_at.asc(), ExternalSyncJob.id.asc())
            .limit(1)
        )
        if job_id is None:
            db.rollback()
            return None
        return self.run_job(db, int(job_id))

    def _process_runner_state_snapshot(
        self,
        sync_outcome: GarminSyncRunOutcome,
    ) -> RunnerStateAutoSnapshotResult:
        snapshot_db: Session | None = None
        try:
            snapshot_db = self.snapshot_session_factory()
            service = self.auto_snapshot_service_factory(snapshot_db)
            return service.process_garmin_sync_outcome(
                user_id=sync_outcome.user_id,
                sync_job_id=sync_outcome.job_id,
                sync_run_id=sync_outcome.sync_run_id,
                committed=sync_outcome.committed,
                material_change_count=sync_outcome.runner_state_affecting_change_count,
            )
        except Exception as exc:
            if snapshot_db is not None:
                snapshot_db.rollback()
            logger.warning(
                "Runner-state auto snapshot pipeline boundary failed job_id=%s "
                "sync_run_id=%s error_code=%s exception_type=%s",
                sync_outcome.job_id,
                sync_outcome.sync_run_id,
                "AUTO_SNAPSHOT_PIPELINE_FAILED",
                type(exc).__name__,
            )
            return RunnerStateAutoSnapshotResult(
                status=RunnerStateAutoSnapshotStatus.FAILED_NON_BLOCKING,
                receipt_id=None,
                snapshot_id=None,
                trigger_reference=build_garmin_sync_trigger_reference(sync_outcome.sync_run_id),
                error_code="AUTO_SNAPSHOT_PIPELINE_FAILED",
            )
        finally:
            if snapshot_db is not None:
                snapshot_db.close()
