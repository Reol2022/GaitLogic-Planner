from __future__ import annotations

from sqlalchemy.orm import Session

from planner_core.database.models import ExternalSyncJob
from server.common.exceptions import BadRequestError, NotFoundError
from server.integrations.activity_sync.registry import ProviderRegistry, get_provider_registry
from server.services import garmin_sync_service


class ActivitySyncPipeline:
    """Provider-neutral sync job runner.

    v0.9.4 keeps Garmin's mature matching/import implementation in place and
    routes it through this pipeline. Future providers can add their own generic
    processing path behind the same interface.
    """

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or get_provider_registry()

    def run_job(self, db: Session, job_id: int) -> None:
        job = db.get(ExternalSyncJob, job_id)
        if job is None:
            raise NotFoundError("同步任务不存在。")
        self.registry.get(job.provider)
        if job.provider == "garmin":
            garmin_sync_service.run_sync_job(db, job_id)
            return
        raise BadRequestError("该平台暂未接入通用同步流水线。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")
