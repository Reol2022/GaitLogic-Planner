from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from planner_core.config import get_settings
from planner_core.database.models import (
    ExternalAccountConnection,
    ExternalActivity,
    ExternalActivityLap,
    ExternalActivityRaw,
    ExternalActivityResolution,
    ExternalSyncJob,
    PlannedWorkout,
    TrainingCycle,
    UserAccount,
    WorkoutLog,
    WorkoutLogExternalActivity,
)
from planner_core.enums import PlannedWorkoutLifecycleStatus, PainScaleVersion, TrainingCycleStatus, WorkoutStatusNormalized
from server.common.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError, TooManyRequestsError
from server.integrations.activity_provider import GarminActivityProvider, MockActivityProvider, ProviderActivity, ProviderError
from server.integrations.activity_sync.outcome import GarminSyncRunOutcome, WorkoutLogMaterialChangeTracker
from server.schemas.garmin_sync import (
    ExternalActivityRead,
    GarminActivityReconcileRequest,
    GarminActivityReconcileSummary,
    ExternalSyncJobRead,
    GarminActivityResolutionRequest,
    GarminConnectRequest,
    GarminConnectResponse,
    GarminConnectionStatus,
    GarminMfaRequest,
    GarminSyncSettingsUpdate,
    GarminSyncRequest,
)
from server.services.runner_state_snapshot_receipt_query_service import (
    RunnerStateSnapshotReceiptQueryService,
)
from server.services.training_cycle_lifecycle_service import resolve_cycle_for_date
from server.services.token_encryption_service import decrypt_token_payload, encrypt_token_payload

PROVIDER = "garmin"
ACTIVE_STATUSES = {"connected", "reauthentication_required", "temporarily_unavailable"}
RUNNING_JOB_STATUSES = {"queued", "running"}
SUPPORTED_ACTIVITY_TYPES = {
    "outdoor_running",
    "track_running",
    "treadmill_running",
    "indoor_running",
    "trail_running",
    "running_unknown",
}
NORMALIZATION_VERSION = "garmin-activity-v1"
SEGMENTATION_VERSION = "garmin-segmentation-v1"
CLASSIFICATION_VERSION = "garmin-segment-classification-v1"
logger = logging.getLogger(__name__)


def _job_read(db: Session, user_id: int, job: ExternalSyncJob) -> ExternalSyncJobRead:
    read = ExternalSyncJobRead.model_validate(job)
    return RunnerStateSnapshotReceiptQueryService(db).attach_to_job(
        user_id=user_id,
        job=read,
    )


def _job_reads(
    db: Session,
    user_id: int,
    jobs: list[ExternalSyncJob],
) -> list[ExternalSyncJobRead]:
    reads = [ExternalSyncJobRead.model_validate(job) for job in jobs]
    return RunnerStateSnapshotReceiptQueryService(db).attach_to_jobs(
        user_id=user_id,
        jobs=reads,
    )


def get_connection_status(db: Session, user_id: int) -> GarminConnectionStatus:
    connection = _active_connection(db, user_id)
    if connection is None:
        return GarminConnectionStatus(connected=False)
    return GarminConnectionStatus(
        connected=connection.status == "connected",
        connection_id=connection.id,
        status=connection.status,
        provider=connection.provider,
        region=connection.region,
        masked_account_identifier=connection.masked_account_identifier,
        auto_import_enabled=connection.auto_import_enabled,
        auto_sync_enabled=connection.auto_sync_enabled,
        auto_sync_last_run_at=connection.auto_sync_last_run_at,
        last_authenticated_at=connection.last_authenticated_at,
        last_successful_sync_at=connection.last_successful_sync_at,
        last_error_code=connection.last_error_code,
        last_error_at=connection.last_error_at,
    )


def connect(db: Session, current_user: UserAccount, payload: GarminConnectRequest) -> GarminConnectResponse:
    provider = GarminActivityProvider()
    try:
        auth_result = provider.authenticate(payload.username, payload.password, payload.region)
    except ProviderError as exc:
        _raise_provider_app_error(exc)
    if auth_result.status == "mfa_required":
        return GarminConnectResponse(status="mfa_required", mfa_token=auth_result.mfa_token, safe_message=auth_result.safe_message)
    if not auth_result.token_payload or not auth_result.account_identifier:
        raise ServiceUnavailableError("Garmin 认证没有返回可保存会话。", error_code="AUTHENTICATION_REQUIRED")
    connection = _upsert_connection(
        db,
        user_id=current_user.id,
        account_identifier=auth_result.account_identifier,
        masked_account_identifier=auth_result.masked_account_identifier,
        token_payload=auth_result.token_payload,
        region=payload.region,
        connector_version=provider.connector_version,
    )
    return GarminConnectResponse(status="connected", connection=get_connection_status(db, connection.user_id))


def submit_mfa(db: Session, current_user: UserAccount, payload: GarminMfaRequest) -> GarminConnectResponse:
    provider = GarminActivityProvider()
    try:
        auth_result = provider.submit_mfa(payload.mfa_token, payload.mfa_code)
    except ProviderError as exc:
        _raise_provider_app_error(exc)
    if not auth_result.token_payload or not auth_result.account_identifier:
        raise ServiceUnavailableError("Garmin MFA 认证没有返回可保存会话。", error_code="AUTHENTICATION_REQUIRED")
    connection = _upsert_connection(
        db,
        user_id=current_user.id,
        account_identifier=auth_result.account_identifier,
        masked_account_identifier=auth_result.masked_account_identifier,
        token_payload=auth_result.token_payload,
        region=None,
        connector_version=provider.connector_version,
    )
    return GarminConnectResponse(status="connected", connection=get_connection_status(db, connection.user_id))


def disconnect(db: Session, user_id: int) -> GarminConnectionStatus:
    connection = _require_connection(db, user_id)
    connection.status = "disconnected"
    connection.encrypted_token_payload = None
    connection.active_user_provider_key = None
    connection.active_account_key = None
    connection.disconnected_at = datetime.utcnow()
    db.commit()
    return get_connection_status(db, user_id)


def update_sync_settings(db: Session, user_id: int, payload: GarminSyncSettingsUpdate) -> GarminConnectionStatus:
    connection = _require_connection(db, user_id)
    connection.auto_import_enabled = payload.auto_import_enabled
    db.commit()
    return get_connection_status(db, user_id)


def enqueue_sync_job(
    db: Session,
    user_id: int,
    payload: GarminSyncRequest,
    idempotency_key: str | None = None,
    *,
    _sync_run_id: str | None = None,
) -> ExternalSyncJobRead:
    connection = _require_connection(db, user_id)
    if connection.status != "connected":
        raise BadRequestError("Garmin 连接需要重新认证。", error_code="REAUTHENTICATION_REQUIRED")
    existing_running = db.scalar(
        select(ExternalSyncJob)
        .where(
            ExternalSyncJob.connection_id == connection.id,
            ExternalSyncJob.status.in_(RUNNING_JOB_STATUSES),
        )
        .order_by(ExternalSyncJob.created_at.desc())
    )
    if existing_running is not None:
        return _job_read(db, user_id, existing_running)
    start, end, mode = _resolve_sync_range(connection, payload)
    if idempotency_key:
        existing = db.scalar(
            select(ExternalSyncJob).where(
                ExternalSyncJob.connection_id == connection.id,
                ExternalSyncJob.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return _job_read(db, user_id, existing)
    job = ExternalSyncJob(
        user_id=user_id,
        connection_id=connection.id,
        provider=PROVIDER,
        sync_mode=mode,
        requested_start=start,
        requested_end=end,
        status="queued",
        idempotency_key=idempotency_key,
        sync_run_id=_sync_run_id or str(uuid4()),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_read(db, user_id, job)


def list_sync_jobs(db: Session, user_id: int, limit: int = 20) -> list[ExternalSyncJobRead]:
    jobs = db.scalars(
        select(ExternalSyncJob)
        .where(ExternalSyncJob.user_id == user_id, ExternalSyncJob.provider == PROVIDER)
        .order_by(ExternalSyncJob.created_at.desc())
        .limit(min(limit, 100))
    ).all()
    return _job_reads(db, user_id, list(jobs))


def get_sync_job(db: Session, user_id: int, job_id: int) -> ExternalSyncJobRead:
    job = _get_user_job(db, user_id, job_id)
    return _job_read(db, user_id, job)


def retry_sync_job(db: Session, user_id: int, job_id: int) -> ExternalSyncJobRead:
    job = _get_user_job(db, user_id, job_id)
    if job.status not in {"failed", "partially_succeeded"}:
        raise BadRequestError("只有失败或部分成功的同步任务可以重试。")
    request = GarminSyncRequest(sync_mode=job.sync_mode, start=job.requested_start, end=job.requested_end)
    return enqueue_sync_job(
        db,
        user_id,
        request,
        idempotency_key=f"retry-{uuid4()}",
        _sync_run_id=job.sync_run_id,
    )


def list_activities(db: Session, user_id: int, limit: int = 50) -> list[ExternalActivityRead]:
    activities = db.scalars(
        select(ExternalActivity)
        .where(ExternalActivity.user_id == user_id, ExternalActivity.provider == PROVIDER)
        .order_by(ExternalActivity.start_time_local.desc())
        .limit(min(limit, 200))
    ).all()
    return [ExternalActivityRead.model_validate(activity) for activity in activities]


def reconcile_activities(
    db: Session,
    user_id: int,
    payload: GarminActivityReconcileRequest,
) -> GarminActivityReconcileSummary:
    activities = _reconcile_scope(db, user_id, payload)
    if payload.dry_run:
        return _dry_run_reconcile(db, user_id, activities)

    adapter = _ReconcileJobAdapter(user_id=user_id)
    for activity in activities:
        previous = _activity_state(activity)
        _match_and_apply(db, adapter, activity, same_day_activity_count=_same_day_activity_count(activities, activity))
        db.add(
            ExternalActivityResolution(
                user_id=user_id,
                external_activity_id=activity.id,
                workout_log_id=activity.workout_log_id,
                action="reconcile",
                previous_state_json=previous,
                new_state_json=_activity_state(activity),
                reason="Garmin 活动重处理",
                actor_type="system",
            )
        )
    db.commit()
    return GarminActivityReconcileSummary(
        dry_run=False,
        activity_count=len(activities),
        estimated_session_count=_estimate_session_count(activities),
        estimated_matched_plan_count=adapter.matched_count,
        estimated_merged_existing_log_count=adapter.duplicate_count,
        estimated_unplanned_log_count=adapter.unplanned_count,
        needs_review_count=adapter.needs_review_count,
        conflict_count=adapter.needs_review_count,
        applied_count=adapter.matched_count + adapter.unplanned_count + adapter.duplicate_count,
    )


def resolve_activity(
    db: Session,
    user_id: int,
    activity_id: int,
    payload: GarminActivityResolutionRequest,
) -> ExternalActivityRead:
    activity = db.scalar(
        select(ExternalActivity)
        .where(ExternalActivity.id == activity_id, ExternalActivity.user_id == user_id)
        .options(selectinload(ExternalActivity.workout_links))
    )
    if activity is None:
        raise NotFoundError("活动不存在或不属于当前用户。")
    previous = _activity_state(activity)
    if payload.action == "ignore":
        _set_activity_state(activity, "ignored", "not_applied", processing_status="ignored")
        activity.ignored_at = datetime.utcnow()
    elif payload.action == "mark_unplanned":
        existing_log = _find_nearby_unplanned_log(db, activity)
        log = _create_or_fill_log(db, activity, None, "high", auto_applied=False)
        _set_activity_state(activity, "unplanned", "log_merged" if existing_log else "log_created", processing_status="unplanned")
        activity.workout_log_id = log.id
        activity.composite_session_key = _session_key(log)
    elif payload.action == "link_to_plan":
        if payload.planned_workout_id is None:
            raise BadRequestError("关联计划时必须提供 planned_workout_id。")
        plan = _get_user_plan(db, user_id, payload.planned_workout_id)
        existing_log_id = plan.workout_log.id if plan.workout_log else None
        log = _create_or_fill_log(db, activity, plan, "high", auto_applied=False)
        _set_activity_state(activity, "matched", "log_merged" if existing_log_id else "log_created", processing_status="matched")
        activity.planned_workout_id = plan.id
        activity.workout_log_id = log.id
        activity.composite_session_key = _session_key(log)
    else:
        raise BadRequestError("不支持的处理动作。")
    db.add(
        ExternalActivityResolution(
            user_id=user_id,
            external_activity_id=activity.id,
            workout_log_id=activity.workout_log_id,
            action=payload.action,
            previous_state_json=previous,
            new_state_json=_activity_state(activity),
            reason=payload.reason,
            actor_type="user",
        )
    )
    db.commit()
    db.refresh(activity)
    return ExternalActivityRead.model_validate(activity)


def claim_sync_job(db: Session, job_id: int) -> bool:
    """Atomically grant execution rights to one queued-job claimant."""

    now = datetime.utcnow()
    result = db.execute(
        update(ExternalSyncJob)
        .where(ExternalSyncJob.id == job_id, ExternalSyncJob.status == "queued")
        .values(
            status="running",
            attempt_count=ExternalSyncJob.attempt_count + 1,
            started_at=now,
            locked_at=now,
            is_committed=False,
            committed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    claimed = result.rowcount == 1
    if claimed:
        db.commit()
        db.expire_all()
    else:
        db.rollback()
    return claimed


def run_sync_job(db: Session, job_id: int) -> GarminSyncRunOutcome:
    if not claim_sync_job(db, job_id):
        existing = db.get(ExternalSyncJob, job_id)
        if existing is None:
            raise NotFoundError("同步任务不存在。")
        return _outcome_from_job(existing, claimed=False, warning_codes=("JOB_NOT_CLAIMED",))

    job = db.scalar(
        select(ExternalSyncJob)
        .where(ExternalSyncJob.id == job_id)
        .options(selectinload(ExternalSyncJob.connection))
    )
    if job is None:
        raise NotFoundError("同步任务不存在。")

    tracker = WorkoutLogMaterialChangeTracker()
    unchanged_activity_count = 0
    successful_activity_count = 0
    fetched_count = 0
    failed_count = 0
    try:
        connection = job.connection
        token_payload = decrypt_token_payload(connection.encrypted_token_payload)
        provider = _provider_for_connection(connection)
        provider.restore_session(token_payload)
        activities = provider.fetch_activities(
            job.requested_start or datetime.utcnow() - timedelta(days=90),
            job.requested_end or datetime.utcnow(),
        )
        same_day_counts = Counter(activity.start_time_local.date() for activity in activities)
        fetched_count = len(activities)
        job.fetched_count = fetched_count
        activity_errors: list[str] = []
        for provider_activity in activities:
            activity_tracker = WorkoutLogMaterialChangeTracker()
            try:
                with db.begin_nested():
                    result = _process_provider_activity(
                        db,
                        job,
                        provider_activity,
                        provider.connector_version,
                        same_day_activity_count=same_day_counts[provider_activity.start_time_local.date()],
                        material_tracker=activity_tracker,
                    )
                successful_activity_count += 1
                if activity_tracker.has_material_change():
                    tracker.merge(activity_tracker)
                else:
                    unchanged_activity_count += 1
                if result == "created":
                    job.created_count += 1
                elif result == "updated":
                    job.updated_count += 1
                elif result == "duplicate":
                    job.duplicate_count += 1
            except Exception as exc:
                logger.exception("Failed to process Garmin activity id=%s", provider_activity.external_activity_id)
                failed_count += 1
                job.failed_count = failed_count
                activity_errors.append(f"{provider_activity.external_activity_id}: {_safe_activity_error(exc)}")

        if fetched_count > 0 and successful_activity_count == 0:
            db.rollback()
            return _mark_job_failed(
                db,
                job_id,
                "ALL_ACTIVITIES_FAILED",
                "所有 Garmin 活动均处理失败，本次同步未提交训练数据。",
                fetched_count=fetched_count,
                failed_count=failed_count,
            )

        refreshed_token = provider.refresh_session()
        if refreshed_token:
            connection.encrypted_token_payload = encrypt_token_payload(refreshed_token)
            connection.token_key_version = get_settings().garmin_token_key_version
        if failed_count == 0 or successful_activity_count > 0:
            connection.last_successful_sync_at = datetime.utcnow()
        job.status = "succeeded" if failed_count == 0 else "partially_succeeded"
        if activity_errors:
            job.error_code = "ACTIVITY_PROCESSING_PARTIAL_FAILURE"
            preview = "; ".join(activity_errors[:5])
            suffix = " ..." if len(activity_errors) > 5 else ""
            job.safe_error_message = _truncate_error_message(
                f"{len(activity_errors)} 条 Garmin 活动处理失败：{preview}{suffix}"
            )
        material_counts = tracker.counts()
        job.created_log_count = material_counts.created_log_count
        job.updated_log_count = material_counts.updated_log_count
        job.unchanged_activity_count = unchanged_activity_count
        job.runner_state_affecting_change_count = material_counts.runner_state_affecting_change_count
        job.is_committed = True
        job.committed_at = datetime.utcnow()
        job.finished_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            logger.exception("Garmin sync final commit failed id=%s", job_id)
            db.rollback()
            return _mark_job_failed(
                db,
                job_id,
                "SYNC_COMMIT_FAILED",
                "Garmin 同步数据提交失败，请稍后重试。",
                fetched_count=fetched_count,
                failed_count=failed_count,
            )
        warning_codes = ("ACTIVITY_PROCESSING_PARTIAL_FAILURE",) if activity_errors else ()
        return _outcome_from_job(job, claimed=True, warning_codes=warning_codes)
    except ProviderError as exc:
        db.rollback()
        return _mark_job_failed(
            db,
            job_id,
            exc.code,
            exc.safe_message,
            fetched_count=fetched_count,
            failed_count=failed_count,
        )
    except BadRequestError as exc:
        db.rollback()
        return _mark_job_failed(
            db,
            job_id,
            str(exc.error_code or "SYNC_FAILED"),
            exc.message,
            fetched_count=fetched_count,
            failed_count=failed_count,
        )
    except Exception:
        logger.exception("Garmin sync job failed unexpectedly id=%s", job_id)
        db.rollback()
        return _mark_job_failed(
            db,
            job_id,
            "SYNC_FAILED",
            "Garmin 同步任务执行失败，请稍后重试。",
            fetched_count=fetched_count,
            failed_count=failed_count,
        )


def _process_provider_activity(
    db: Session,
    job: ExternalSyncJob,
    provider_activity: ProviderActivity,
    connector_version: str,
    *,
    same_day_activity_count: int = 1,
    material_tracker: WorkoutLogMaterialChangeTracker | None = None,
) -> str:
    raw_payload = _desensitize_payload(provider_activity.raw_payload)
    payload_hash = _payload_hash(raw_payload)
    raw = db.scalar(
        select(ExternalActivityRaw).where(
            ExternalActivityRaw.provider == PROVIDER,
            ExternalActivityRaw.external_activity_id == provider_activity.external_activity_id,
            ExternalActivityRaw.payload_hash == payload_hash,
        )
    )
    if raw is None:
        raw = ExternalActivityRaw(
            user_id=job.user_id,
            connection_id=job.connection_id,
            sync_job_id=job.id,
            provider=PROVIDER,
            external_activity_id=provider_activity.external_activity_id,
            payload_hash=payload_hash,
            raw_payload_json=raw_payload,
            fetched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=get_settings().garmin_raw_retention_days),
        )
        db.add(raw)
        db.flush()
    activity = db.scalar(
        select(ExternalActivity).where(
            ExternalActivity.provider == PROVIDER,
            ExternalActivity.external_activity_id == provider_activity.external_activity_id,
        )
    )
    is_duplicate = activity is not None and activity.payload_hash == payload_hash
    if activity is None:
        activity = _new_external_activity(job, raw, provider_activity, payload_hash, connector_version)
        db.add(activity)
        db.flush()
        result = "created"
    else:
        _update_external_activity(activity, job, raw, provider_activity, payload_hash, connector_version)
        result = "duplicate" if is_duplicate else "updated"
    _replace_laps(activity, provider_activity)
    if job.connection.auto_import_enabled:
        _match_and_apply(
            db,
            job,
            activity,
            same_day_activity_count=same_day_activity_count,
            material_tracker=material_tracker,
        )
    else:
        _mark_activity_import_deferred(activity)
    db.flush()
    return result


def _new_external_activity(
    job: ExternalSyncJob,
    raw: ExternalActivityRaw,
    provider_activity: ProviderActivity,
    payload_hash: str,
    connector_version: str,
) -> ExternalActivity:
    activity = ExternalActivity(
        user_id=job.user_id,
        connection_id=job.connection_id,
        sync_job_id=job.id,
        raw_activity_id=raw.id,
        provider=PROVIDER,
        external_activity_id=provider_activity.external_activity_id,
        connector_version=connector_version,
        normalization_version=NORMALIZATION_VERSION,
        segmentation_version=SEGMENTATION_VERSION,
        classification_version=CLASSIFICATION_VERSION,
        payload_hash=payload_hash,
        fetched_at=datetime.utcnow(),
        activity_name=provider_activity.activity_name,
        activity_type=_normalize_activity_type(provider_activity.activity_type),
        activity_subtype=provider_activity.activity_subtype,
        start_time_utc=provider_activity.start_time_utc,
        start_time_local=provider_activity.start_time_local,
        timezone=provider_activity.timezone,
        activity_date=provider_activity.start_time_local.date(),
        processing_status="synced",
        field_sources_json={},
    )
    _copy_activity_metrics(activity, provider_activity)
    return activity


def _update_external_activity(
    activity: ExternalActivity,
    job: ExternalSyncJob,
    raw: ExternalActivityRaw,
    provider_activity: ProviderActivity,
    payload_hash: str,
    connector_version: str,
) -> None:
    activity.sync_job_id = job.id
    activity.raw_activity_id = raw.id
    activity.connector_version = connector_version
    activity.payload_hash = payload_hash
    activity.source_updated_at = provider_activity.source_updated_at
    activity.fetched_at = datetime.utcnow()
    activity.activity_name = provider_activity.activity_name
    activity.activity_type = _normalize_activity_type(provider_activity.activity_type)
    activity.activity_subtype = provider_activity.activity_subtype
    activity.start_time_utc = provider_activity.start_time_utc
    activity.start_time_local = provider_activity.start_time_local
    activity.timezone = provider_activity.timezone
    activity.activity_date = provider_activity.start_time_local.date()
    _copy_activity_metrics(activity, provider_activity)


def _copy_activity_metrics(activity: ExternalActivity, provider_activity: ProviderActivity) -> None:
    for field in [
        "distance_m",
        "duration_seconds",
        "timer_time_seconds",
        "moving_time_seconds",
        "elapsed_time_seconds",
        "average_speed_mps",
        "max_speed_mps",
        "average_heart_rate_bpm",
        "max_heart_rate_bpm",
        "min_heart_rate_bpm",
        "average_cadence_spm",
        "max_cadence_spm",
        "elevation_gain_m",
        "elevation_loss_m",
        "calories_kcal",
        "average_stride_length_m",
        "average_vertical_ratio_percent",
        "average_vertical_oscillation_cm",
        "average_ground_contact_time_ms",
        "ground_contact_balance_percent",
        "average_running_power_w",
        "max_running_power_w",
        "garmin_primary_benefit",
        "garmin_aerobic_training_effect",
        "garmin_anaerobic_training_effect",
        "garmin_training_load",
        "garmin_recovery_time_seconds",
    ]:
        setattr(activity, field, getattr(provider_activity, field))
    activity.average_pace_seconds_per_km = _pace(provider_activity.average_speed_mps)
    activity.best_pace_seconds_per_km = _pace(provider_activity.max_speed_mps)
    activity.quality_warnings_json = _quality_warnings(activity)
    activity.data_quality = "warning" if activity.quality_warnings_json else "valid"
    activity.field_sources_json = {field: PROVIDER for field in ["distance_m", "duration_seconds", "average_heart_rate_bpm"]}


def _replace_laps(activity: ExternalActivity, provider_activity: ProviderActivity) -> None:
    activity.laps.clear()
    high_distance = Decimal("0")
    has_high_segments = False
    used_lap_indices: set[int] = set()
    for lap in provider_activity.laps:
        lap_index = _unique_lap_index(lap.lap_index, used_lap_indices)
        pace = _pace(lap.average_speed_mps)
        if lap.segment_role in {"threshold", "interval", "repetition"} and lap.classification_confidence == "high" and lap.distance_m is not None:
            high_distance += lap.distance_m
            has_high_segments = True
        activity.laps.append(
            ExternalActivityLap(
                lap_index=lap_index,
                external_lap_id=lap.external_lap_id,
                start_time=lap.start_time,
                start_offset_seconds=lap.start_offset_seconds,
                distance_m=lap.distance_m,
                duration_seconds=lap.duration_seconds,
                timer_time_seconds=lap.timer_time_seconds,
                moving_time_seconds=lap.moving_time_seconds,
                average_speed_mps=lap.average_speed_mps,
                average_pace_seconds_per_km=pace,
                average_heart_rate_bpm=lap.average_heart_rate_bpm,
                max_heart_rate_bpm=lap.max_heart_rate_bpm,
                average_cadence_spm=lap.average_cadence_spm,
                elevation_gain_m=lap.elevation_gain_m,
                lap_type=lap.lap_type,
                workout_step_type=lap.workout_step_type,
                segment_role=lap.segment_role,
                classification_source=lap.classification_source,
                classification_confidence=lap.classification_confidence,
                data_quality=lap.data_quality,
            )
        )
    activity.high_intensity_distance_m = high_distance if has_high_segments else None


def _unique_lap_index(value: int | None, used_indices: set[int]) -> int:
    candidate = value if value and value > 0 else len(used_indices) + 1
    while candidate in used_indices:
        candidate += 1
    used_indices.add(candidate)
    return candidate


def _match_and_apply(
    db: Session,
    job: ExternalSyncJob,
    activity: ExternalActivity,
    *,
    same_day_activity_count: int = 1,
    material_tracker: WorkoutLogMaterialChangeTracker | None = None,
) -> None:
    if activity.activity_type not in SUPPORTED_ACTIVITY_TYPES:
        _set_activity_state(activity, "ignored", "not_applied", processing_status="ignored")
        job.ignored_count += 1
        return

    existing_link = db.scalar(
        select(WorkoutLogExternalActivity).where(WorkoutLogExternalActivity.external_activity_id == activity.id)
    )
    if existing_link is not None:
        log = db.get(WorkoutLog, existing_link.workout_log_id)
        if log is not None:
            if material_tracker is not None:
                material_tracker.capture_before(log)
            _recalculate_log_from_linked_activities(db, log)
            activity.workout_log_id = log.id
            activity.planned_workout_id = log.planned_workout_id
            _set_activity_state(
                activity,
                "matched" if log.planned_workout_id else "unplanned",
                "linked_existing",
                processing_status="matched" if log.planned_workout_id else "unplanned",
            )
            job.duplicate_count += 1
            return

    candidates = _candidate_plans_for_activity(db, job.user_id, activity)
    if len(candidates) > 1:
        _mark_activity_needs_review(db, activity, "同日存在多个计划，无法唯一匹配。")
        job.needs_review_count += 1
        return

    if same_day_activity_count > 1 and not candidates and _has_large_gap_unplanned_activity(db, job.user_id, activity):
        _mark_activity_needs_review(db, activity, "同日存在间隔较大的多段活动，需人工确认是否双跑。")
        job.needs_review_count += 1
        return

    plan = candidates[0] if len(candidates) == 1 else None
    confidence = "high"
    existing_log_id = plan.workout_log.id if plan and plan.workout_log else None
    if existing_log_id is None and plan is None:
        existing_unplanned_log = _find_nearby_unplanned_log(db, activity)
        existing_log_id = existing_unplanned_log.id if existing_unplanned_log else None
    log = _create_or_fill_log(
        db,
        activity,
        plan,
        confidence,
        auto_applied=True,
        material_tracker=material_tracker,
    )
    activity.workout_log_id = log.id
    activity.planned_workout_id = plan.id if plan else None
    _set_activity_state(
        activity,
        "matched" if plan else "unplanned",
        "log_merged" if existing_log_id else "log_created",
        processing_status="matched" if plan else "unplanned",
    )
    activity.match_confidence = confidence
    activity.composite_session_key = _session_key(log)
    if plan:
        job.matched_count += 1
    else:
        job.unplanned_count += 1


def _mark_activity_import_deferred(activity: ExternalActivity) -> None:
    if activity.apply_status in {"log_created", "log_merged", "linked_existing"}:
        return
    activity.processing_status = "synced"
    activity.resolution_status = "pending"
    activity.apply_status = "not_applied"
    activity.match_confidence = None
    activity.planned_workout_id = None
    activity.workout_log_id = None
    activity.composite_session_key = None


def _candidate_plans_for_activity(db: Session, user_id: int, activity: ExternalActivity) -> list[PlannedWorkout]:
    return list(
        db.scalars(
            select(PlannedWorkout)
            .join(TrainingCycle, TrainingCycle.id == PlannedWorkout.cycle_id)
            .options(selectinload(PlannedWorkout.workout_log))
            .where(
                PlannedWorkout.user_id == user_id,
                PlannedWorkout.workout_date == activity.activity_date,
                PlannedWorkout.lifecycle_status == PlannedWorkoutLifecycleStatus.planned,
                TrainingCycle.status.in_([TrainingCycleStatus.active, TrainingCycleStatus.completed]),
            )
            .order_by(PlannedWorkout.session_index, PlannedWorkout.sort_order, PlannedWorkout.id)
        )
    )


def _mark_activity_needs_review(db: Session, activity: ExternalActivity, reason: str) -> None:
    _set_activity_state(activity, "needs_review", "not_applied", processing_status="needs_review")
    activity.match_confidence = "low"
    activity.planned_workout_id = None
    activity.workout_log_id = None
    if activity.id is not None:
        db.execute(delete(WorkoutLogExternalActivity).where(WorkoutLogExternalActivity.external_activity_id == activity.id))
    db.add(
        ExternalActivityResolution(
            user_id=activity.user_id,
            external_activity_id=activity.id,
            action="needs_review",
            previous_state_json={},
            new_state_json=_activity_state(activity),
            reason=reason,
            actor_type="system",
        )
    )


def _create_or_fill_log(
    db: Session,
    activity: ExternalActivity,
    plan: PlannedWorkout | None,
    confidence: str,
    *,
    auto_applied: bool,
    material_tracker: WorkoutLogMaterialChangeTracker | None = None,
) -> WorkoutLog:
    log = plan.workout_log if plan and plan.workout_log else None
    resolved_cycle_id = plan.cycle_id if plan else None
    cycle_assignment_status = "assigned" if plan else "unassigned"
    if plan is None:
        resolved_cycle, cycle_assignment_status = resolve_cycle_for_date(db, activity.user_id, activity.activity_date)
        resolved_cycle_id = resolved_cycle.id if resolved_cycle else None
    if log is None:
        log = db.scalar(
            select(WorkoutLog).where(
                WorkoutLog.user_id == activity.user_id,
                WorkoutLog.external_activity_id == activity.external_activity_id,
                WorkoutLog.source_type == "garmin_sync",
            )
        )
    if log is None and plan is None:
        log = _find_nearby_unplanned_log(db, activity)
    if log is None:
        log = WorkoutLog(
            user_id=activity.user_id,
            planned_workout_id=plan.id if plan else None,
            cycle_id=resolved_cycle_id,
            cycle_assignment_status=cycle_assignment_status,
            status_raw="completed",
            status_normalized=WorkoutStatusNormalized.completed_normal,
            pain_scale_version=PainScaleVersion.native_0_10,
            activity_date=activity.activity_date,
            start_time=activity.start_time_local.time().replace(microsecond=0),
            timezone=activity.timezone,
            session_index=plan.session_index if plan else 1,
            sport_type="running",
            workout_type=plan.main_type_raw if plan else None,
            title=activity.activity_name,
            is_unplanned=plan is None,
            source_type="garmin_sync",
            external_activity_id=activity.external_activity_id,
            activity_fingerprint=_payload_hash({"provider": PROVIDER, "id": activity.external_activity_id}),
            field_sources_json={},
            subjective_status="pending",
        )
        db.add(log)
        db.flush()
        if material_tracker is not None:
            material_tracker.capture_created(log)
    else:
        if material_tracker is not None:
            material_tracker.capture_before(log)
        if plan is not None:
            log.cycle_id = plan.cycle_id
            log.cycle_assignment_status = "assigned"
        elif log.cycle_id is None and log.cycle_assignment_status != "needs_review":
            log.cycle_id = resolved_cycle_id
            log.cycle_assignment_status = cycle_assignment_status
    existing_link = db.scalar(
        select(WorkoutLogExternalActivity).where(
            WorkoutLogExternalActivity.external_activity_id == activity.id,
        )
    )
    if existing_link is None:
        db.add(
            WorkoutLogExternalActivity(
                user_id=activity.user_id,
                workout_log_id=log.id,
                external_activity_id=activity.id,
                link_type="matched" if plan else "unplanned",
                match_confidence=confidence,
                resolution_status="auto_applied" if auto_applied else "user_confirmed",
                field_sources_json={"objective_fields": PROVIDER},
            )
        )
        db.flush()
    _recalculate_log_from_linked_activities(db, log)
    return log


def _find_nearby_unplanned_log(db: Session, activity: ExternalActivity) -> WorkoutLog | None:
    max_gap = timedelta(minutes=get_settings().garmin_composite_activity_max_gap_minutes)
    candidates = list(
        db.scalars(
            select(WorkoutLog).where(
                WorkoutLog.user_id == activity.user_id,
                WorkoutLog.planned_workout_id.is_(None),
                WorkoutLog.source_type == "garmin_sync",
                WorkoutLog.is_unplanned.is_(True),
                WorkoutLog.activity_date == activity.activity_date,
            )
        )
    )
    for log in candidates:
        if _time_gap(_activity_start(activity), _activity_end(activity), _log_start(activity, log), _log_end(activity, log)) <= max_gap:
            return log
    return None


def _has_large_gap_unplanned_activity(db: Session, user_id: int, activity: ExternalActivity) -> bool:
    max_gap = timedelta(minutes=get_settings().garmin_composite_activity_max_gap_minutes)
    existing = list(
        db.scalars(
            select(ExternalActivity).where(
                ExternalActivity.user_id == user_id,
                ExternalActivity.activity_date == activity.activity_date,
                ExternalActivity.id != activity.id,
                ExternalActivity.apply_status.in_(["log_created", "log_merged", "linked_existing"]),
            )
        )
    )
    return any(
        _time_gap(_activity_start(activity), _activity_end(activity), _activity_start(item), _activity_end(item)) > max_gap
        for item in existing
    )


def _recalculate_log_from_linked_activities(db: Session, log: WorkoutLog) -> None:
    activities = list(
        db.scalars(
            select(ExternalActivity)
            .join(WorkoutLogExternalActivity, WorkoutLogExternalActivity.external_activity_id == ExternalActivity.id)
            .where(WorkoutLogExternalActivity.workout_log_id == log.id)
            .order_by(ExternalActivity.start_time_local, ExternalActivity.id)
        )
    )
    if not activities:
        return
    total_distance_m = sum((item.distance_m or Decimal("0")) for item in activities)
    total_duration = sum((item.timer_time_seconds or item.duration_seconds or 0) for item in activities)
    moving_time = sum((item.moving_time_seconds or 0) for item in activities) or None
    elapsed_time = sum((item.elapsed_time_seconds or 0) for item in activities) or None
    elevation_gain = sum((item.elevation_gain_m or 0) for item in activities) or None
    calories = sum((item.calories_kcal or 0) for item in activities) or None
    cadence_values = [item.average_cadence_spm for item in activities if item.average_cadence_spm is not None]
    max_cadence_values = [item.max_cadence_spm for item in activities if item.max_cadence_spm is not None]
    max_hr_values = [item.max_heart_rate_bpm for item in activities if item.max_heart_rate_bpm is not None]
    avg_hr = _weighted_average(
        [(item.average_heart_rate_bpm, item.timer_time_seconds or item.duration_seconds) for item in activities]
    )
    mapping = {
        "actual_distance_km": (total_distance_m / Decimal("1000")) if total_distance_m > 0 else None,
        "actual_duration_seconds": total_duration or None,
        "moving_time_seconds": moving_time,
        "elapsed_time_seconds": elapsed_time,
        "avg_pace_seconds_per_km": int((Decimal(total_duration) / (total_distance_m / Decimal("1000"))).to_integral_value()) if total_distance_m > 0 and total_duration else None,
        "avg_heart_rate": avg_hr,
        "max_heart_rate": max(max_hr_values) if max_hr_values else None,
        "average_cadence_spm": int(sum(cadence_values) / len(cadence_values)) if cadence_values else None,
        "max_cadence_spm": max(max_cadence_values) if max_cadence_values else None,
        "elevation_gain_m": elevation_gain,
        "calories_kcal": calories,
    }
    sources = dict(log.field_sources_json or {})
    for field, value in mapping.items():
        if value is not None and _can_fill_garmin_field(log, field, sources):
            setattr(log, field, value)
            sources[field] = PROVIDER
    if log.status_normalized == WorkoutStatusNormalized.not_started:
        log.status_normalized = WorkoutStatusNormalized.completed_normal
    if log.rpe is None or log.review_note is None:
        log.subjective_status = "pending"
    else:
        log.subjective_status = "completed"
    log.field_sources_json = sources


def _can_fill_garmin_field(log: WorkoutLog, field: str, sources: dict[str, str]) -> bool:
    return getattr(log, field) is None or sources.get(field) in {PROVIDER, "garmin_sync"}


def _weighted_average(values: list[tuple[int | None, int | None]]) -> int | None:
    weighted_sum = 0
    weight_total = 0
    for value, weight in values:
        if value is None or not weight:
            continue
        weighted_sum += value * weight
        weight_total += weight
    return int(round(weighted_sum / weight_total)) if weight_total else None


def _activity_start(activity: ExternalActivity) -> datetime:
    return activity.start_time_local


def _activity_end(activity: ExternalActivity) -> datetime:
    return activity.start_time_local + timedelta(seconds=activity.timer_time_seconds or activity.duration_seconds or 0)


def _log_start(activity: ExternalActivity, log: WorkoutLog) -> datetime:
    if log.activity_date and log.start_time:
        return datetime.combine(log.activity_date, log.start_time)
    return activity.start_time_local


def _log_end(activity: ExternalActivity, log: WorkoutLog) -> datetime:
    return _log_start(activity, log) + timedelta(seconds=log.actual_duration_seconds or 0)


def _time_gap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> timedelta:
    if end_a < start_b:
        return start_b - end_a
    if end_b < start_a:
        return start_a - end_b
    return timedelta(0)


def _session_key(log: WorkoutLog) -> str:
    return f"workout-log:{log.id}"


def _set_activity_state(activity: ExternalActivity, resolution_status: str, apply_status: str, *, processing_status: str | None = None) -> None:
    activity.resolution_status = resolution_status
    activity.apply_status = apply_status
    activity.processing_status = processing_status or resolution_status


def _fill_objective_log_fields(log: WorkoutLog, activity: ExternalActivity) -> None:
    mapping = {
        "actual_distance_km": (activity.distance_m / Decimal("1000")) if activity.distance_m is not None else None,
        "actual_duration_seconds": activity.timer_time_seconds or activity.duration_seconds,
        "moving_time_seconds": activity.moving_time_seconds,
        "elapsed_time_seconds": activity.elapsed_time_seconds,
        "avg_pace_seconds_per_km": activity.average_pace_seconds_per_km,
        "avg_heart_rate": activity.average_heart_rate_bpm,
        "max_heart_rate": activity.max_heart_rate_bpm,
        "average_cadence_spm": activity.average_cadence_spm,
        "max_cadence_spm": activity.max_cadence_spm,
        "elevation_gain_m": activity.elevation_gain_m,
        "calories_kcal": activity.calories_kcal,
    }
    sources = dict(log.field_sources_json or {})
    for field, value in mapping.items():
        if value is not None and getattr(log, field) is None:
            setattr(log, field, value)
            sources[field] = PROVIDER
    log.field_sources_json = sources


def _upsert_connection(
    db: Session,
    *,
    user_id: int,
    account_identifier: str,
    masked_account_identifier: str | None,
    token_payload: dict[str, Any],
    region: str | None,
    connector_version: str,
) -> ExternalAccountConnection:
    account_hash = _hash_identifier(account_identifier)
    active_account_key = f"{PROVIDER}:{account_hash}"
    owned = db.scalar(
        select(ExternalAccountConnection).where(
            ExternalAccountConnection.active_account_key == active_account_key,
            ExternalAccountConnection.user_id != user_id,
        )
    )
    if owned is not None:
        raise BadRequestError("该 Garmin 账号已绑定其他用户。", error_code="GARMIN_ACCOUNT_ALREADY_BOUND")
    connection = _active_connection(db, user_id)
    if connection is None:
        connection = ExternalAccountConnection(user_id=user_id, provider=PROVIDER)
        db.add(connection)
    now = datetime.utcnow()
    connection.status = "connected"
    connection.region = region
    connection.masked_account_identifier = masked_account_identifier
    connection.account_identifier_hash = account_hash
    connection.active_user_provider_key = f"{user_id}:{PROVIDER}"
    connection.active_account_key = active_account_key
    connection.encrypted_token_payload = encrypt_token_payload(token_payload)
    connection.token_key_version = get_settings().garmin_token_key_version
    connection.connector_version = connector_version
    connection.last_authenticated_at = now
    connection.last_error_code = None
    connection.last_error_at = None
    connection.disconnected_at = None
    db.commit()
    db.refresh(connection)
    return connection


def _provider_for_connection(connection: ExternalAccountConnection):
    if connection.connector_version and connection.connector_version.startswith("mock-"):
        return MockActivityProvider()
    return GarminActivityProvider()


def _active_connection(db: Session, user_id: int) -> ExternalAccountConnection | None:
    return db.scalar(
        select(ExternalAccountConnection)
        .where(
            ExternalAccountConnection.user_id == user_id,
            ExternalAccountConnection.provider == PROVIDER,
            ExternalAccountConnection.status.in_(ACTIVE_STATUSES),
        )
        .order_by(ExternalAccountConnection.created_at.desc())
    )


def _require_connection(db: Session, user_id: int) -> ExternalAccountConnection:
    connection = _active_connection(db, user_id)
    if connection is None:
        raise NotFoundError("尚未连接 Garmin。", error_code="AUTHENTICATION_REQUIRED")
    return connection


def _get_user_job(db: Session, user_id: int, job_id: int) -> ExternalSyncJob:
    job = db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.id == job_id, ExternalSyncJob.user_id == user_id))
    if job is None:
        raise NotFoundError("同步任务不存在或不属于当前用户。")
    return job


def _get_user_plan(db: Session, user_id: int, plan_id: int) -> PlannedWorkout:
    plan = db.scalar(
        select(PlannedWorkout)
        .options(selectinload(PlannedWorkout.workout_log))
        .where(PlannedWorkout.id == plan_id, PlannedWorkout.user_id == user_id)
    )
    if plan is None:
        raise NotFoundError("训练计划不存在或不属于当前用户。")
    return plan


class _ReconcileJobAdapter:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.matched_count = 0
        self.unplanned_count = 0
        self.needs_review_count = 0
        self.ignored_count = 0
        self.duplicate_count = 0


def _reconcile_scope(db: Session, user_id: int, payload: GarminActivityReconcileRequest) -> list[ExternalActivity]:
    stmt = select(ExternalActivity).where(ExternalActivity.user_id == user_id, ExternalActivity.provider == PROVIDER)
    if payload.activity_ids:
        stmt = stmt.where(ExternalActivity.id.in_(payload.activity_ids))
    if payload.start_date:
        stmt = stmt.where(ExternalActivity.activity_date >= payload.start_date)
    if payload.end_date:
        stmt = stmt.where(ExternalActivity.activity_date <= payload.end_date)
    stmt = stmt.order_by(ExternalActivity.activity_date, ExternalActivity.start_time_local, ExternalActivity.id)
    return list(db.scalars(stmt))


def _dry_run_reconcile(db: Session, user_id: int, activities: list[ExternalActivity]) -> GarminActivityReconcileSummary:
    matched_plan_count = 0
    merged_existing_log_count = 0
    unplanned_count = 0
    needs_review_count = 0
    for activity in activities:
        if activity.resolution_status == "ignored" or activity.processing_status == "ignored":
            continue
        candidates = _candidate_plans_for_activity(db, user_id, activity)
        existing_link = db.scalar(
            select(WorkoutLogExternalActivity).where(WorkoutLogExternalActivity.external_activity_id == activity.id)
        )
        if existing_link is not None:
            merged_existing_log_count += 1
        elif len(candidates) > 1:
            needs_review_count += 1
        elif len(candidates) == 1:
            matched_plan_count += 1
            if candidates[0].workout_log:
                merged_existing_log_count += 1
        else:
            unplanned_count += 1
    return GarminActivityReconcileSummary(
        dry_run=True,
        activity_count=len(activities),
        estimated_session_count=_estimate_session_count(activities),
        estimated_matched_plan_count=matched_plan_count,
        estimated_merged_existing_log_count=merged_existing_log_count,
        estimated_unplanned_log_count=unplanned_count,
        needs_review_count=needs_review_count,
        conflict_count=needs_review_count,
    )


def _same_day_activity_count(activities: list[ExternalActivity], activity: ExternalActivity) -> int:
    return sum(1 for item in activities if item.activity_date == activity.activity_date)


def _estimate_session_count(activities: list[ExternalActivity]) -> int:
    if not activities:
        return 0
    sessions = 0
    max_gap = timedelta(minutes=get_settings().garmin_composite_activity_max_gap_minutes)
    by_day: dict[date, list[ExternalActivity]] = {}
    for activity in activities:
        by_day.setdefault(activity.activity_date, []).append(activity)
    for rows in by_day.values():
        previous: ExternalActivity | None = None
        for activity in sorted(rows, key=lambda item: (item.start_time_local, item.id)):
            if previous is None or _time_gap(_activity_start(activity), _activity_end(activity), _activity_start(previous), _activity_end(previous)) > max_gap:
                sessions += 1
            previous = activity
    return sessions


def _resolve_sync_range(connection: ExternalAccountConnection, payload: GarminSyncRequest) -> tuple[datetime, datetime, str]:
    now = datetime.utcnow()
    settings = get_settings()
    mode = payload.sync_mode
    if mode == "incremental":
        if connection.last_successful_sync_at is None:
            mode = "initial_backfill"
            return now - timedelta(days=settings.garmin_initial_sync_days), now, mode
        return connection.last_successful_sync_at - timedelta(days=settings.garmin_incremental_overlap_days), now, mode
    if mode == "initial_backfill":
        return now - timedelta(days=settings.garmin_initial_sync_days), now, mode
    if mode == "recent_7d":
        return now - timedelta(days=7), now, mode
    if mode == "recent_30d":
        return now - timedelta(days=30), now, mode
    if mode == "custom_range":
        if payload.start is None or payload.end is None:
            raise BadRequestError("自定义同步范围必须提供开始和结束时间。", error_code="SYNC_RANGE_REQUIRED")
        if payload.end < payload.start:
            raise BadRequestError("同步结束时间不能早于开始时间。", error_code="SYNC_RANGE_INVALID")
        if payload.end - payload.start > timedelta(days=settings.garmin_custom_sync_max_days):
            raise BadRequestError("同步范围过大。", error_code="SYNC_RANGE_TOO_LARGE")
        return payload.start, payload.end, mode
    raise BadRequestError("不支持的同步模式。", error_code="SYNC_MODE_INVALID")


def _normalize_activity_type(value: str | None) -> str:
    text = (value or "").lower()
    if text in SUPPORTED_ACTIVITY_TYPES:
        return text
    if "trail" in text:
        return "trail_running"
    if "treadmill" in text:
        return "treadmill_running"
    if "indoor" in text:
        return "indoor_running"
    if "track" in text:
        return "track_running"
    if "run" in text:
        return "running_unknown"
    return text or "unknown"


def _quality_warnings(activity: ExternalActivity) -> list[str]:
    warnings: list[str] = []
    if activity.distance_m is None:
        warnings.append("MISSING_DISTANCE")
    if activity.duration_seconds is None and activity.timer_time_seconds is None:
        warnings.append("MISSING_DURATION")
    if activity.average_heart_rate_bpm is None:
        warnings.append("MISSING_HEART_RATE")
    if activity.distance_m is None and activity.duration_seconds is None:
        warnings.append("INCOMPLETE_ACTIVITY")
    return warnings


def _pace(speed_mps: Decimal | None) -> int | None:
    if speed_mps is None or speed_mps <= 0:
        return None
    return int((Decimal("1000") / speed_mps).to_integral_value())


def _desensitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blocked_fragments = ("token", "cookie", "password", "serial", "polyline", "coordinate", "longitude", "latitude", "gps")
    clean: dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if any(fragment in key.lower() for fragment in blocked_fragments):
            continue
        clean[key] = value
    return clean


def _payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _activity_state(activity: ExternalActivity) -> dict[str, Any]:
    return {
        "processing_status": activity.processing_status,
        "resolution_status": activity.resolution_status,
        "apply_status": activity.apply_status,
        "composite_session_key": activity.composite_session_key,
        "planned_workout_id": activity.planned_workout_id,
        "workout_log_id": activity.workout_log_id,
        "ignored_at": activity.ignored_at.isoformat() if activity.ignored_at else None,
    }


def _outcome_from_job(
    job: ExternalSyncJob,
    *,
    claimed: bool,
    warning_codes: tuple[str, ...] = (),
) -> GarminSyncRunOutcome:
    return GarminSyncRunOutcome(
        job_id=int(job.id),
        user_id=int(job.user_id),
        provider=job.provider,
        sync_run_id=job.sync_run_id,
        claimed=claimed,
        committed=job.is_committed,
        final_status=job.status,
        created_log_count=job.created_log_count,
        updated_log_count=job.updated_log_count,
        unchanged_activity_count=job.unchanged_activity_count,
        runner_state_affecting_change_count=job.runner_state_affecting_change_count,
        warning_codes=warning_codes,
    )


def _mark_job_failed(
    db: Session,
    job_id: int,
    code: str,
    message: str,
    *,
    fetched_count: int = 0,
    failed_count: int = 0,
) -> GarminSyncRunOutcome:
    """Persist failure metadata only after the training transaction was rolled back."""

    job = db.scalar(
        select(ExternalSyncJob)
        .where(ExternalSyncJob.id == job_id)
        .options(selectinload(ExternalSyncJob.connection))
    )
    if job is None:
        raise NotFoundError("同步任务不存在。")
    now = datetime.utcnow()
    job.status = "failed"
    job.error_code = code
    job.safe_error_message = _truncate_error_message(message)
    job.fetched_count = max(fetched_count, 0)
    job.failed_count = max(failed_count, 0)
    job.is_committed = False
    job.committed_at = None
    job.created_log_count = 0
    job.updated_log_count = 0
    job.unchanged_activity_count = 0
    job.runner_state_affecting_change_count = 0
    job.finished_at = now
    job.connection.last_error_code = code
    job.connection.last_error_at = now
    if code in {"TOKEN_DECRYPTION_FAILED", "REAUTHENTICATION_REQUIRED", "AUTHENTICATION_REQUIRED"}:
        job.connection.status = "reauthentication_required"
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _outcome_from_job(job, claimed=True, warning_codes=(code,))


def _safe_activity_error(exc: Exception) -> str:
    name = exc.__class__.__name__
    text = str(exc).strip()
    if "Duplicate" in text or "IntegrityError" in name:
        return "活动数据重复"
    if "DataError" in name:
        return "活动字段格式异常"
    if "OperationalError" in name:
        return "数据库暂时不可用"
    return "活动数据处理失败"


def _truncate_error_message(message: str, limit: int = 255) -> str:
    return message if len(message) <= limit else f"{message[: limit - 1]}…"


def _raise_provider_app_error(exc: ProviderError) -> None:
    if exc.code in {"AUTHENTICATION_REQUIRED", "MFA_REQUIRED", "REAUTHENTICATION_REQUIRED"}:
        raise BadRequestError(exc.safe_message, error_code=exc.code) from exc
    if exc.code == "RATE_LIMITED":
        raise TooManyRequestsError(exc.safe_message, error_code=exc.code) from exc
    raise ServiceUnavailableError(exc.safe_message, error_code=exc.code) from exc
