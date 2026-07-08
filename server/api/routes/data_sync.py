from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.integrations.activity_sync.facade import DataSyncFacade
from server.integrations.activity_sync.schemas import (
    DataSyncActivityActionRequest,
    DataSyncActivityListResponse,
    DataSyncChallengeRequest,
    DataSyncConnectRequest,
    DataSyncConnectResponse,
    DataSyncConnectionRead,
    DataSyncJobListResponse,
    DataSyncRequest,
    ExternalActivityRead,
    ExternalSyncJobRead,
    ProviderListResponse,
)
from server.schemas.simplified_workflow import DataSyncPreferencesUpdate, DataSyncSummaryRead
from server.common.exceptions import NotFoundError
from planner_core.database.models import ExternalAccountConnection
from sqlalchemy import select
from server.integrations.activity_sync.workers.sync_worker import run_sync_job_in_background
from server.services import simplified_workflow_service
from server.services.feature_access_service import assert_data_sync_available

router = APIRouter(prefix="/data-sync", tags=["data-sync"])


def _facade(db: Session, current_user: UserAccount) -> DataSyncFacade:
    return DataSyncFacade(db, current_user)


@router.get("/providers", response_model=ProviderListResponse)
def list_providers(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ProviderListResponse:
    assert_data_sync_available(db, current_user)
    return ProviderListResponse(providers=_facade(db, current_user).list_providers())


@router.get("/summary", response_model=DataSyncSummaryRead)
def get_data_sync_summary(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncSummaryRead:
    assert_data_sync_available(db, current_user)
    return simplified_workflow_service.get_data_sync_summary(db, current_user.id)


@router.get("/connections", response_model=list[DataSyncConnectionRead])
def list_connections(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[DataSyncConnectionRead]:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).list_connections()


@router.get("/connections/{provider_key}", response_model=DataSyncConnectionRead)
def get_connection(
    provider_key: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncConnectionRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).get_connection(provider_key)


@router.post("/connections/{provider_key}/connect", response_model=DataSyncConnectResponse)
def connect(
    provider_key: str,
    payload: DataSyncConnectRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncConnectResponse:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).connect(provider_key, payload)


@router.post("/connections/{provider_key}/challenge", response_model=DataSyncConnectResponse)
def challenge(
    provider_key: str,
    payload: DataSyncChallengeRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncConnectResponse:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).challenge(provider_key, payload)


@router.post("/connections/{provider_key}/disconnect", response_model=DataSyncConnectionRead)
def disconnect(
    provider_key: str,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncConnectionRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).disconnect(provider_key)


@router.post("/connections/{provider_key}/sync", response_model=ExternalSyncJobRead)
def create_sync_job(
    provider_key: str,
    payload: DataSyncRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_data_sync_available(db, current_user)
    job = _facade(db, current_user).create_sync_job(provider_key, payload, idempotency_key)
    if job.status == "queued":
        background_tasks.add_task(run_sync_job_in_background, job.id)
    return job


@router.get("/sync-jobs", response_model=DataSyncJobListResponse)
def list_sync_jobs(
    provider: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncJobListResponse:
    assert_data_sync_available(db, current_user)
    return DataSyncJobListResponse(jobs=_facade(db, current_user).list_sync_jobs(limit=limit, provider_key=provider))


@router.get("/sync-jobs/{job_id}", response_model=ExternalSyncJobRead)
def get_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).get_sync_job(job_id)


@router.post("/sync-jobs/{job_id}/retry", response_model=ExternalSyncJobRead)
def retry_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).retry_sync_job(job_id)


@router.get("/activities", response_model=DataSyncActivityListResponse)
def list_activities(
    provider: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncActivityListResponse:
    assert_data_sync_available(db, current_user)
    return DataSyncActivityListResponse(activities=_facade(db, current_user).list_activities(limit=limit, provider_key=provider))


@router.get("/activities/{activity_id}", response_model=ExternalActivityRead)
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).get_activity(activity_id)


@router.post("/activities/{activity_id}/reprocess", response_model=ExternalActivityRead)
def reprocess_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).reprocess_activity(activity_id)


@router.post("/activities/{activity_id}/ignore", response_model=ExternalActivityRead)
def ignore_activity(
    activity_id: int,
    payload: DataSyncActivityActionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).ignore_activity(activity_id, payload)


@router.post("/activities/{activity_id}/restore", response_model=ExternalActivityRead)
def restore_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_data_sync_available(db, current_user)
    return _facade(db, current_user).restore_activity(activity_id)


@router.patch("/connections/{provider_key}/preferences", response_model=DataSyncConnectionRead)
def update_connection_preferences(
    provider_key: str,
    payload: DataSyncPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> DataSyncConnectionRead:
    assert_data_sync_available(db, current_user)
    connection = db.scalar(
        select(ExternalAccountConnection).where(
            ExternalAccountConnection.user_id == current_user.id,
            ExternalAccountConnection.provider == provider_key,
            ExternalAccountConnection.status != "disconnected",
        )
    )
    if connection is None:
        raise NotFoundError("尚未连接该数据平台。", error_code="AUTHENTICATION_REQUIRED")
    if payload.auto_import_enabled is not None:
        connection.auto_import_enabled = payload.auto_import_enabled
    if payload.auto_sync_enabled is not None:
        connection.auto_sync_enabled = payload.auto_sync_enabled
    db.commit()
    return _facade(db, current_user).get_connection(provider_key)
