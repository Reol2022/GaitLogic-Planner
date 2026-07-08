from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import ExternalActivity, ExternalSyncJob, UserAccount
from server.common.exceptions import BadRequestError, NotFoundError
from server.integrations.activity_sync.capabilities import ProviderDescriptor
from server.integrations.activity_sync.registry import ProviderRegistry, get_provider_registry
from server.integrations.activity_sync.schemas import (
    DataSyncActivityActionRequest,
    DataSyncChallengeRequest,
    DataSyncConnectRequest,
    DataSyncConnectResponse,
    DataSyncConnectionRead,
    DataSyncRequest,
)
from server.schemas.garmin_sync import (
    ExternalActivityRead,
    ExternalSyncJobRead,
    GarminActivityReconcileRequest,
    GarminActivityResolutionRequest,
    GarminConnectRequest,
    GarminConnectResponse,
    GarminConnectionStatus,
    GarminMfaRequest,
    GarminSyncRequest,
)
from server.services import garmin_sync_service


class DataSyncFacade:
    def __init__(self, db: Session, current_user: UserAccount, registry: ProviderRegistry | None = None) -> None:
        self.db = db
        self.current_user = current_user
        self.registry = registry or get_provider_registry()

    def list_providers(self) -> list[ProviderDescriptor]:
        return self.registry.list_descriptors()

    def get_provider(self, provider_key: str) -> ProviderDescriptor:
        return self.registry.get(provider_key).descriptor()

    def get_connection(self, provider_key: str) -> DataSyncConnectionRead:
        provider = self.registry.get(provider_key)
        if provider.provider_key == "garmin":
            return _connection_from_garmin(garmin_sync_service.get_connection_status(self.db, self.current_user.id), provider.descriptor())
        return DataSyncConnectionRead(
            connected=False,
            provider=provider.provider_key,
            status=provider.descriptor().status,
            descriptor=provider.descriptor(),
        )

    def list_connections(self) -> list[DataSyncConnectionRead]:
        return [self.get_connection(descriptor.key) for descriptor in self.list_providers()]

    def connect(self, provider_key: str, payload: DataSyncConnectRequest) -> DataSyncConnectResponse:
        provider = self.registry.get(provider_key)
        if provider.provider_key != "garmin":
            provider.begin_connection(payload.username, payload.password, payload.region)
            return DataSyncConnectResponse(status="connected", connection=self.get_connection(provider.provider_key))
        response = garmin_sync_service.connect(
            self.db,
            self.current_user,
            GarminConnectRequest(username=payload.username, password=payload.password, region=payload.region),
        )
        return _connect_response_from_garmin(response, provider.descriptor())

    def challenge(self, provider_key: str, payload: DataSyncChallengeRequest) -> DataSyncConnectResponse:
        provider = self.registry.get(provider_key)
        if provider.provider_key != "garmin":
            provider.continue_connection(payload.mfa_token, payload.mfa_code)
            return DataSyncConnectResponse(status="connected", connection=self.get_connection(provider.provider_key))
        response = garmin_sync_service.submit_mfa(
            self.db,
            self.current_user,
            GarminMfaRequest(mfa_token=payload.mfa_token, mfa_code=payload.mfa_code),
        )
        return _connect_response_from_garmin(response, provider.descriptor())

    def disconnect(self, provider_key: str) -> DataSyncConnectionRead:
        provider = self.registry.get(provider_key)
        if provider.provider_key == "garmin":
            return _connection_from_garmin(
                garmin_sync_service.disconnect(self.db, self.current_user.id),
                provider.descriptor(),
            )
        return DataSyncConnectionRead(connected=False, provider=provider.provider_key, status="disconnected", descriptor=provider.descriptor())

    def create_sync_job(
        self,
        provider_key: str,
        payload: DataSyncRequest,
        idempotency_key: str | None = None,
    ) -> ExternalSyncJobRead:
        provider = self.registry.get(provider_key)
        if provider.provider_key != "garmin":
            raise BadRequestError("该平台暂未开放同步任务。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")
        return garmin_sync_service.enqueue_sync_job(
            self.db,
            self.current_user.id,
            GarminSyncRequest(sync_mode=payload.sync_mode, start=payload.start, end=payload.end),
            idempotency_key,
        )

    def list_sync_jobs(self, limit: int = 20, provider_key: str | None = None) -> list[ExternalSyncJobRead]:
        if provider_key:
            provider = self.registry.get(provider_key)
            if provider.provider_key == "garmin":
                return garmin_sync_service.list_sync_jobs(self.db, self.current_user.id, limit=limit)
        stmt = (
            select(ExternalSyncJob)
            .where(ExternalSyncJob.user_id == self.current_user.id)
            .order_by(ExternalSyncJob.created_at.desc())
            .limit(min(limit, 100))
        )
        if provider_key:
            stmt = stmt.where(ExternalSyncJob.provider == provider_key)
        return [ExternalSyncJobRead.model_validate(job) for job in self.db.scalars(stmt).all()]

    def get_sync_job(self, job_id: int) -> ExternalSyncJobRead:
        job = self.db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.id == job_id, ExternalSyncJob.user_id == self.current_user.id))
        if job is None:
            raise NotFoundError("同步任务不存在或不属于当前用户。")
        return ExternalSyncJobRead.model_validate(job)

    def retry_sync_job(self, job_id: int) -> ExternalSyncJobRead:
        job = self.db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.id == job_id, ExternalSyncJob.user_id == self.current_user.id))
        if job is None:
            raise NotFoundError("同步任务不存在或不属于当前用户。")
        self.registry.get(job.provider)
        if job.provider == "garmin":
            return garmin_sync_service.retry_sync_job(self.db, self.current_user.id, job_id)
        raise BadRequestError("该平台暂不支持重试。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")

    def list_activities(self, limit: int = 50, provider_key: str | None = None) -> list[ExternalActivityRead]:
        if provider_key:
            provider = self.registry.get(provider_key)
            if provider.provider_key == "garmin":
                return garmin_sync_service.list_activities(self.db, self.current_user.id, limit=limit)
        stmt = (
            select(ExternalActivity)
            .where(ExternalActivity.user_id == self.current_user.id)
            .order_by(ExternalActivity.start_time_local.desc())
            .limit(min(limit, 200))
        )
        if provider_key:
            stmt = stmt.where(ExternalActivity.provider == provider_key)
        return [ExternalActivityRead.model_validate(activity) for activity in self.db.scalars(stmt).all()]

    def get_activity(self, activity_id: int) -> ExternalActivityRead:
        activity = self._get_activity_model(activity_id)
        return ExternalActivityRead.model_validate(activity)

    def reprocess_activity(self, activity_id: int) -> ExternalActivityRead:
        activity = self._get_activity_model(activity_id)
        self.registry.get(activity.provider)
        if activity.provider == "garmin":
            garmin_sync_service.reconcile_activities(
                self.db,
                self.current_user.id,
                GarminActivityReconcileRequest(dry_run=False, activity_ids=[activity_id]),
            )
            return self.get_activity(activity_id)
        raise BadRequestError("该平台暂不支持重新处理。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")

    def ignore_activity(self, activity_id: int, payload: DataSyncActivityActionRequest | None = None) -> ExternalActivityRead:
        activity = self._get_activity_model(activity_id)
        self.registry.get(activity.provider)
        if activity.provider == "garmin":
            return garmin_sync_service.resolve_activity(
                self.db,
                self.current_user.id,
                activity_id,
                GarminActivityResolutionRequest(action="ignore", reason=payload.reason if payload else None),
            )
        raise BadRequestError("该平台暂不支持忽略活动。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")

    def restore_activity(self, activity_id: int) -> ExternalActivityRead:
        activity = self._get_activity_model(activity_id)
        activity.ignored_at = None
        activity.processing_status = "pending"
        activity.resolution_status = "pending"
        activity.apply_status = "not_applied"
        self.db.commit()
        return self.reprocess_activity(activity_id)

    def resolve_garmin_activity(self, activity_id: int, payload: GarminActivityResolutionRequest) -> ExternalActivityRead:
        return garmin_sync_service.resolve_activity(self.db, self.current_user.id, activity_id, payload)

    def reconcile_garmin_activities(self, payload: GarminActivityReconcileRequest):
        return garmin_sync_service.reconcile_activities(self.db, self.current_user.id, payload)

    def update_garmin_sync_settings(self, payload) -> GarminConnectionStatus:
        return garmin_sync_service.update_sync_settings(self.db, self.current_user.id, payload)

    def _get_activity_model(self, activity_id: int) -> ExternalActivity:
        activity = self.db.scalar(select(ExternalActivity).where(ExternalActivity.id == activity_id, ExternalActivity.user_id == self.current_user.id))
        if activity is None:
            raise NotFoundError("活动不存在或不属于当前用户。")
        return activity


def _connection_from_garmin(status: GarminConnectionStatus, descriptor: ProviderDescriptor) -> DataSyncConnectionRead:
    return DataSyncConnectionRead(
        connected=status.connected,
        connection_id=status.connection_id,
        provider=status.provider,
        status=status.status,
        region=status.region,
        masked_account_identifier=status.masked_account_identifier,
        auto_import_enabled=status.auto_import_enabled,
        auto_sync_enabled=status.auto_sync_enabled,
        auto_sync_last_run_at=status.auto_sync_last_run_at,
        last_authenticated_at=status.last_authenticated_at,
        last_successful_sync_at=status.last_successful_sync_at,
        last_error_code=status.last_error_code,
        last_error_at=status.last_error_at,
        descriptor=descriptor,
    )


def _connect_response_from_garmin(response: GarminConnectResponse, descriptor: ProviderDescriptor) -> DataSyncConnectResponse:
    return DataSyncConnectResponse(
        status=response.status,
        connection=_connection_from_garmin(response.connection, descriptor) if response.connection else None,
        mfa_token=response.mfa_token,
        safe_message=response.safe_message,
    )
