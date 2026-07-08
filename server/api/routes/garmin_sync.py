from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from planner_core.database.models import UserAccount
from server.api.deps import get_current_user, get_db
from server.schemas.garmin_sync import (
    GarminActivityReconcileRequest,
    GarminActivityReconcileSummary,
    ExternalActivityRead,
    ExternalSyncJobRead,
    GarminActivityResolutionRequest,
    GarminConnectRequest,
    GarminConnectResponse,
    GarminConnectionStatus,
    GarminMfaRequest,
    GarminSyncSettingsUpdate,
    GarminSyncRequest,
)
from server.integrations.activity_sync.facade import DataSyncFacade
from server.integrations.activity_sync.schemas import DataSyncChallengeRequest, DataSyncConnectRequest, DataSyncRequest
from server.integrations.activity_sync.workers.sync_worker import run_sync_job_in_background
from server.services.feature_access_service import assert_garmin_sync_available

router = APIRouter(prefix="/integrations/garmin", tags=["garmin-sync"])


def _facade(db: Session, current_user: UserAccount) -> DataSyncFacade:
    return DataSyncFacade(db, current_user)


@router.get("/status", response_model=GarminConnectionStatus)
def get_status(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    connection = _facade(db, current_user).get_connection("garmin")
    return GarminConnectionStatus(**connection.model_dump(exclude={"descriptor"}))


@router.post("/connect", response_model=GarminConnectResponse)
def connect(
    payload: GarminConnectRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectResponse:
    assert_garmin_sync_available(db, current_user)
    response = _facade(db, current_user).connect(
        "garmin",
        DataSyncConnectRequest(username=payload.username, password=payload.password, region=payload.region),
    )
    return GarminConnectResponse(
        status=response.status,
        connection=GarminConnectionStatus(**response.connection.model_dump(exclude={"descriptor"})) if response.connection else None,
        mfa_token=response.mfa_token,
        safe_message=response.safe_message,
    )


@router.post("/connect/mfa", response_model=GarminConnectResponse)
def submit_mfa(
    payload: GarminMfaRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectResponse:
    assert_garmin_sync_available(db, current_user)
    response = _facade(db, current_user).challenge(
        "garmin",
        DataSyncChallengeRequest(mfa_token=payload.mfa_token, mfa_code=payload.mfa_code),
    )
    return GarminConnectResponse(
        status=response.status,
        connection=GarminConnectionStatus(**response.connection.model_dump(exclude={"descriptor"})) if response.connection else None,
        mfa_token=response.mfa_token,
        safe_message=response.safe_message,
    )


@router.post("/disconnect", response_model=GarminConnectionStatus)
def disconnect(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    connection = _facade(db, current_user).disconnect("garmin")
    return GarminConnectionStatus(**connection.model_dump(exclude={"descriptor"}))


@router.put("/settings", response_model=GarminConnectionStatus)
def update_settings(
    payload: GarminSyncSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).update_garmin_sync_settings(payload)


@router.post("/sync", response_model=ExternalSyncJobRead)
def enqueue_sync(
    payload: GarminSyncRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    job = _facade(db, current_user).create_sync_job(
        "garmin",
        DataSyncRequest(sync_mode=payload.sync_mode, start=payload.start, end=payload.end),
        idempotency_key,
    )
    if job.status == "queued":
        background_tasks.add_task(run_sync_job_in_background, job.id)
    return job


@router.get("/sync-jobs", response_model=list[ExternalSyncJobRead])
def list_sync_jobs(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[ExternalSyncJobRead]:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).list_sync_jobs(provider_key="garmin")


@router.get("/sync-jobs/{job_id}", response_model=ExternalSyncJobRead)
def get_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).get_sync_job(job_id)


@router.post("/sync-jobs/{job_id}/retry", response_model=ExternalSyncJobRead)
def retry_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).retry_sync_job(job_id)


@router.get("/activities", response_model=list[ExternalActivityRead])
def list_activities(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[ExternalActivityRead]:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).list_activities(provider_key="garmin")


@router.post("/activities/reconcile", response_model=GarminActivityReconcileSummary)
def reconcile_activities(
    payload: GarminActivityReconcileRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminActivityReconcileSummary:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).reconcile_garmin_activities(payload)


@router.post("/activities/{activity_id}/resolve", response_model=ExternalActivityRead)
def resolve_activity(
    activity_id: int,
    payload: GarminActivityResolutionRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_garmin_sync_available(db, current_user)
    return _facade(db, current_user).resolve_garmin_activity(activity_id, payload)
