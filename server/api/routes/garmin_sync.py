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
from server.services import garmin_sync_service
from server.services.feature_access_service import assert_garmin_sync_available

router = APIRouter(prefix="/integrations/garmin", tags=["garmin-sync"])


@router.get("/status", response_model=GarminConnectionStatus)
def get_status(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.get_connection_status(db, current_user.id)


@router.post("/connect", response_model=GarminConnectResponse)
def connect(
    payload: GarminConnectRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectResponse:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.connect(db, current_user, payload)


@router.post("/connect/mfa", response_model=GarminConnectResponse)
def submit_mfa(
    payload: GarminMfaRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectResponse:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.submit_mfa(db, current_user, payload)


@router.post("/disconnect", response_model=GarminConnectionStatus)
def disconnect(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.disconnect(db, current_user.id)


@router.put("/settings", response_model=GarminConnectionStatus)
def update_settings(
    payload: GarminSyncSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminConnectionStatus:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.update_sync_settings(db, current_user.id, payload)


@router.post("/sync", response_model=ExternalSyncJobRead)
def enqueue_sync(
    payload: GarminSyncRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    job = garmin_sync_service.enqueue_sync_job(db, current_user.id, payload, idempotency_key)
    if job.status == "queued":
        background_tasks.add_task(garmin_sync_service.run_sync_job_in_background, job.id)
    return job


@router.get("/sync-jobs", response_model=list[ExternalSyncJobRead])
def list_sync_jobs(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[ExternalSyncJobRead]:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.list_sync_jobs(db, current_user.id)


@router.get("/sync-jobs/{job_id}", response_model=ExternalSyncJobRead)
def get_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.get_sync_job(db, current_user.id, job_id)


@router.post("/sync-jobs/{job_id}/retry", response_model=ExternalSyncJobRead)
def retry_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalSyncJobRead:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.retry_sync_job(db, current_user.id, job_id)


@router.get("/activities", response_model=list[ExternalActivityRead])
def list_activities(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[ExternalActivityRead]:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.list_activities(db, current_user.id)


@router.post("/activities/reconcile", response_model=GarminActivityReconcileSummary)
def reconcile_activities(
    payload: GarminActivityReconcileRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> GarminActivityReconcileSummary:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.reconcile_activities(db, current_user.id, payload)


@router.post("/activities/{activity_id}/resolve", response_model=ExternalActivityRead)
def resolve_activity(
    activity_id: int,
    payload: GarminActivityResolutionRequest,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> ExternalActivityRead:
    assert_garmin_sync_available(db, current_user)
    return garmin_sync_service.resolve_activity(db, current_user.id, activity_id, payload)
