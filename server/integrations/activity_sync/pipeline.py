from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import ExternalSyncJob
from server.common.exceptions import BadRequestError, NotFoundError
from server.integrations.activity_sync.registry import ProviderRegistry, get_provider_registry
from server.integrations.activity_sync.outcome import GarminSyncRunOutcome
from server.services import garmin_sync_service


class ActivitySyncPipeline:
    """Provider-neutral sync job runner.

    v0.9.4 keeps Garmin's mature matching/import implementation in place and
    routes it through this pipeline. Future providers can add their own generic
    processing path behind the same interface.
    """

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or get_provider_registry()

    def run_job(self, db: Session, job_id: int) -> GarminSyncRunOutcome:
        job = db.get(ExternalSyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在。")
        self.registry.get(job.provider)
        if job.provider == "garmin":
            return garmin_sync_service.run_sync_job(db, job_id)
        raise BadRequestError("该平台暂未接入通用同步流水线。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")

    def run_next_job(self, db: Session) -> GarminSyncRunOutcome | None:
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
