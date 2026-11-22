"""Persistent coordination only. Provider work stays in the existing pipeline."""
from contextvars import ContextVar
from datetime import datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import select, update, text
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import ExternalAccountConnection, ExternalSyncJob, GarminSmartSyncState, UserAccount
from server.schemas.smart_sync import SmartSyncSettings, SyncFreshness, SyncJobSnapshot

LEASE_SECONDS = 180
execution_lease = ContextVar('garmin_execution_lease', default=None)


def _state(db, connection):
    statement = insert(GarminSmartSyncState).values(connection_id=connection.id, user_id=connection.user_id)
    db.execute(statement.on_duplicate_key_update(connection_id=statement.inserted.connection_id))
    return db.scalar(select(GarminSmartSyncState).where(GarminSmartSyncState.connection_id == connection.id)
        .with_for_update().execution_options(populate_existing=True))


def _latest_scope_job(db, connection, user_id, scope):
    return db.scalar(select(ExternalSyncJob).where(
        ExternalSyncJob.connection_id == connection.id, ExternalSyncJob.user_id == user_id,
        ExternalSyncJob.provider == 'garmin',
        ExternalSyncJob.data_scope.in_(['all', scope]) if scope != 'all' else ExternalSyncJob.data_scope.in_(['all', 'activities', 'recovery']),
    ).order_by(ExternalSyncJob.id.desc()).limit(1))


def _job_receipt(job):
    if job is None:
        return None
    outcome = {'queued': 'QUEUED', 'running': 'RUNNING', 'failed': 'FAILED',
        'cancelled': 'CANCELLED', 'partially_succeeded': 'PARTIAL_SUCCESS'}.get(job.status, 'UNKNOWN')
    if job.status == 'succeeded':
        outcome = ('SUCCEEDED_NO_ACTIVITY_CHANGES' if job.data_scope == 'activities'
            and not job.created_count and not job.updated_count else 'SUCCEEDED')
    return SyncJobSnapshot(job_id=job.id, scope=job.data_scope, status=job.status, outcome=outcome,
        started_at=job.started_at, finished_at=job.finished_at,
        requested_start=job.requested_start, requested_end=job.requested_end,
        fetched_count=job.fetched_count or 0, created_count=job.created_count or 0,
        updated_count=job.updated_count or 0, failed_count=job.failed_count or 0,
        needs_review_count=job.needs_review_count or 0, committed=bool(job.is_committed),
        error_category=error_category(job.error_code) if job.error_code else None)


def status(db, user_id, scope='activities', *, now=None, include_stored_when_disabled=False):
    if scope not in {'activities', 'recovery', 'all'}:
        raise ValueError('Invalid sync scope')
    now = now or datetime.utcnow()
    globally_enabled = get_settings().garmin_smart_sync_enabled
    if not globally_enabled and not include_stored_when_disabled:
        return SyncFreshness(status='DISABLED', sync_status='DISABLED', scope=scope)
    connection = db.scalar(select(ExternalAccountConnection).where(ExternalAccountConnection.user_id == user_id,
        ExternalAccountConnection.provider == 'garmin', ExternalAccountConnection.status != 'disconnected'))
    if connection is None:
        return SyncFreshness(status='NOT_CONNECTED', sync_status='NOT_CONNECTED', scope=scope)
    state = db.get(GarminSmartSyncState, connection.id)
    active = db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.connection_id == connection.id,
        ExternalSyncJob.user_id == user_id,
        ExternalSyncJob.status.in_(['queued', 'running'])).order_by(ExternalSyncJob.id).limit(1))
    job = active if active and (active.data_scope == 'all' or active.data_scope == scope) else None
    latest = {key: _latest_scope_job(db, connection, user_id, key) for key in ('activities', 'recovery')}
    last_job = _latest_scope_job(db, connection, user_id, 'all') if scope == 'all' else latest[scope]
    success = {'activities': connection.last_successful_sync_at, 'recovery': connection.recovery_last_successful_sync_at}
    last = success['recovery' if scope == 'recovery' else 'activities']
    if scope == 'all':
        last = min(success.values()) if all(success.values()) else None
    scopes = success if scope == 'all' else {scope: last}
    # Existing MySQL DATETIME columns round to whole seconds.
    ages = {key: 'UNKNOWN' if stamp is None else 'FRESH' if -timedelta(seconds=1) <= now-stamp < timedelta(minutes=15) else 'STALE'
        for key, stamp in scopes.items()}
    for key in ages:
        candidate = latest[key]
        scope_failed = candidate and (candidate.error_code != 'RECOVERY_SYNC_FAILED' if key == 'activities'
            else candidate.error_code != 'ACTIVITY_PROCESSING_PARTIAL_FAILURE')
        if scope_failed and candidate.status == 'partially_succeeded' and candidate.finished_at and (
            success[key] is None or candidate.finished_at > success[key]):
            # A recently committed subset is not a complete successful fetch.
            ages[key] = 'UNKNOWN'
    freshness = 'STALE' if 'STALE' in ages.values() else 'FRESH' if ages and all(v == 'FRESH' for v in ages.values()) else 'UNKNOWN'
    value = 'FRESH' if last and now-last < timedelta(minutes=15) else 'STALE'
    if not globally_enabled:
        value = 'DISABLED'
    elif not connection.auto_sync_enabled:
        value = 'AUTO_SYNC_DISABLED'
    elif connection.status != 'connected':
        value = 'REAUTH_REQUIRED'
    elif scope == 'recovery' and not (state and state.recovery_enabled):
        value = 'RECOVERY_SYNC_DISABLED'
    elif state and state.next_retry_at and state.next_retry_at > now:
        value = 'BACKOFF'
    if job is not None:
        value = job.status.upper()
    elif active is not None:
        value = 'WAITING_FOR_OTHER_SCOPE'
    return SyncFreshness(status=value, sync_status='IDLE' if value in {'FRESH','STALE'} else value,
        data_freshness=freshness, data_freshness_by_scope=ages, scope=scope, last_success_at=last,
        last_success_by_scope=success if scope == 'all' else {scope: last},
        last_attempt_at=(last_job.started_at or last_job.finished_at) if last_job else None,
        next_retry_at=state.next_retry_at if state else None, error_category=state.error_category if state else None,
        job_id=job.id if job else None, trigger_source=job.trigger_source if job else None,
        last_job=_job_receipt(last_job),
        last_job_by_scope={key: _job_receipt(latest[key]) for key in scopes},
        blocking_job=_job_receipt(active) if active is not None and job is None else None,
        enabled=connection.auto_sync_enabled, interval_minutes=state.interval_minutes if state else 30,
        recovery_enabled=state.recovery_enabled if state else False)


def configure(db, user_id, settings: SmartSyncSettings):
    if not get_settings().garmin_smart_sync_enabled:
        from server.common.exceptions import BadRequestError
        raise BadRequestError('自动同步尚未启用。')
    connection = db.scalar(select(ExternalAccountConnection).where(ExternalAccountConnection.user_id == user_id,
        ExternalAccountConnection.provider == 'garmin', ExternalAccountConnection.status != 'disconnected').with_for_update())
    if connection is None:
        from server.common.exceptions import BadRequestError
        raise BadRequestError('请先连接 Garmin。')
    state = _state(db, connection)
    connection.auto_sync_enabled = settings.enabled
    state.interval_minutes = settings.interval_minutes
    state.recovery_enabled = settings.recovery_enabled
    # Stable per-connection jitter also spreads a simultaneous initial enable.
    state.next_check_at = datetime.utcnow() + timedelta(seconds=connection.id % 300)
    db.commit()
    return status(db, user_id, 'all')


def request_sync(db, user_id, *, trigger, scope='all', now=None):
    if trigger not in {'scheduled', 'login', 'home', 'mcp', 'manual'} or scope not in {'all', 'activities', 'recovery'}:
        raise ValueError('Invalid sync policy input')
    now = now or datetime.utcnow()
    if not get_settings().garmin_smart_sync_enabled:
        return SyncFreshness(status='DISABLED', sync_status='DISABLED', scope=scope)
    # Serialize submissions, including the existing manual enqueue path.
    connection = db.scalar(select(ExternalAccountConnection).where(ExternalAccountConnection.user_id == user_id,
        ExternalAccountConnection.provider == 'garmin', ExternalAccountConnection.status != 'disconnected').with_for_update())
    user = db.get(UserAccount, user_id)
    if connection is None or user is None or user.status != 'active':
        db.rollback()
        return SyncFreshness(status='NOT_CONNECTED', sync_status='NOT_CONNECTED', scope=scope)
    from server.services.feature_access_service import assert_garmin_sync_available
    assert_garmin_sync_available(db, user)
    state = _state(db, connection)
    if scope == 'all' and not state.recovery_enabled:
        scope = 'activities'
    blocked = (connection.status != 'connected' or (not connection.auto_sync_enabled and trigger != 'manual')
        or (scope == 'recovery' and not state.recovery_enabled)
        or (state.next_retry_at and state.next_retry_at > now))
    active = db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.connection_id == connection.id,
        ExternalSyncJob.status.in_(['queued', 'running'])).limit(1))
    success = connection.recovery_last_successful_sync_at if scope == 'recovery' else connection.last_successful_sync_at
    if scope == 'all':
        success = min(success, connection.recovery_last_successful_sync_at) if success and connection.recovery_last_successful_sync_at else None
    window = state.interval_minutes if trigger == 'scheduled' else 15
    fresh = success and now-success < timedelta(minutes=window)
    recent_job = _latest_scope_job(db, connection, user_id, scope)
    attempted_at = (recent_job.started_at or recent_job.finished_at or recent_job.requested_end) if recent_job else None
    if attempted_at is None and _latest_scope_job(db, connection, user_id, 'all') is None:
        # Preserve conservative legacy coordination when no attributable job exists.
        attempted_at = state.last_attempt_at
    recent_attempt = attempted_at and -timedelta(seconds=1) <= now-attempted_at < timedelta(minutes=5)
    due = trigger != 'scheduled' or state.next_check_at is None or state.next_check_at <= now
    submitted = False
    if not blocked and not active and due and (not recent_attempt or trigger == 'manual') and (not fresh or trigger == 'manual'):
        compensate = trigger == 'scheduled' and (state.last_compensation_at is None or now-state.last_compensation_at >= timedelta(days=1))
        job = ExternalSyncJob(user_id=user_id, connection_id=connection.id, provider='garmin', sync_mode='custom_range',
            requested_start=now-timedelta(days=7 if compensate else 3), requested_end=now,
            data_scope=scope, trigger_source=trigger, status='queued', sync_run_id=str(uuid4()))
        db.add(job)
        submitted = True
        state.last_attempt_at = now  # includes submissions, preventing refresh storms
        connection.auto_sync_last_run_at = now
        if compensate:
            state.last_compensation_at = now
    if trigger == 'scheduled' and due and (submitted or fresh):
        # A fresh observation must not postpone the expiry by another full
        # interval. An unrelated active scope must not consume this due check.
        anchor = success if fresh and not submitted else now
        state.next_check_at = anchor + timedelta(minutes=state.interval_minutes, seconds=connection.id % 120)
    db.commit()
    return status(db, user_id, scope, now=now)


def request_safely(session_factory, user_id, *, trigger, scope='all'):
    if not get_settings().garmin_smart_sync_enabled:
        return SyncFreshness(status='DISABLED', sync_status='DISABLED', scope=scope)
    try:
        with session_factory() as db:
            previous = int(db.scalar(text('SELECT @@session.innodb_lock_wait_timeout')))
            db.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
            try:
                return request_sync(db, user_id, trigger=trigger, scope=scope)
            finally:
                db.rollback()
                db.execute(text(f'SET SESSION innodb_lock_wait_timeout={previous}'))
                db.commit()
    except Exception:
        # Failure isolation: never log credentials, raw Provider errors or facts.
        return SyncFreshness(status='CHECK_UNAVAILABLE', sync_status='CHECK_UNAVAILABLE', scope=scope)


def acquire(db, job_id, *, now=None):
    now = now or datetime.utcnow()
    job = db.get(ExternalSyncJob, job_id)
    if job is None or job.status != 'queued':
        db.rollback()
        return None
    connection = db.get(ExternalAccountConnection, job.connection_id)
    if connection is None or connection.status != 'connected':
        job.status = 'failed'
        job.error_code = 'REAUTHENTICATION_REQUIRED'
        job.safe_error_message = 'Garmin 连接已失效，请重新连接后重试。'
        job.finished_at = now
        db.commit()
        return None
    state = _state(db, connection)
    user = db.get(UserAccount, job.user_id)
    revoked = user is None or user.status != 'active'
    if job.trigger_source != 'manual':
        revoked = revoked or not connection.auto_sync_enabled
        if not state.recovery_enabled:
            if job.data_scope == 'recovery':
                revoked = True
            elif job.data_scope == 'all':
                job.data_scope = 'activities'
    if revoked:
        job.status, job.error_code, job.finished_at = 'cancelled', 'SYNC_PERMISSION_REVOKED', now
        db.commit()
        return None
    if state.next_retry_at and state.next_retry_at > now:
        db.rollback()
        return None
    if state.lease_token and state.lease_until and state.lease_until > now:
        db.rollback()
        return None
    if state.active_job_id and state.active_job_id != job_id:
        db.execute(update(ExternalSyncJob).where(ExternalSyncJob.id == state.active_job_id,
            ExternalSyncJob.status == 'running').values(status='failed', error_code='WORKER_LEASE_EXPIRED', finished_at=now))
    token = str(uuid4())
    state.lease_token, state.lease_until, state.active_job_id = token, now+timedelta(seconds=LEASE_SECONDS), job_id
    state.last_attempt_at = now
    db.commit()
    return connection.id, token


def lease_valid(db, lease, *, now=None, lock=False):
    connection_id, token = lease
    statement = select(GarminSmartSyncState).where(GarminSmartSyncState.connection_id == connection_id)
    if lock:
        statement = statement.with_for_update()
    state = db.scalar(statement.execution_options(populate_existing=True))
    return bool(state and state.lease_token == token and state.lease_until and state.lease_until > (now or datetime.utcnow()))


def renew(db, lease):
    connection_id, token = lease
    now = datetime.utcnow()
    result = db.execute(update(GarminSmartSyncState).where(GarminSmartSyncState.connection_id == connection_id,
        GarminSmartSyncState.lease_token == token, GarminSmartSyncState.lease_until > now)
        .values(lease_until=now+timedelta(seconds=LEASE_SECONDS)))
    db.commit()
    return result.rowcount == 1


def error_category(code):
    code = code or ''
    if code.startswith('WORKER_'):
        return 'WORKER'
    if code in {'AUTHENTICATION_REQUIRED', 'REAUTHENTICATION_REQUIRED', 'TOKEN_DECRYPTION_FAILED'}:
        return 'AUTH'
    if 'RATE' in code:
        return 'RATE_LIMIT'
    if 'TIMEOUT' in code or 'NETWORK' in code or 'UNAVAILABLE' in code:
        return 'NETWORK'
    if 'COMMIT' in code or 'DATABASE' in code:
        return 'DATABASE'
    if 'ACTIVIT' in code or 'PARSE' in code:
        return 'PARSING'
    return 'PROVIDER'


def release(db, lease, job_id):
    if not lease_valid(db, lease, lock=True):
        db.rollback()
        return
    state = db.get(GarminSmartSyncState, lease[0])
    job = db.get(ExternalSyncJob, job_id)
    connection = db.get(ExternalAccountConnection, lease[0])
    if job and job.status == 'running':
        # Graceful interruptions execute finally too: do not strand a job.
        job.status = 'failed'
        job.error_code = 'WORKER_INTERRUPTED'
        job.safe_error_message = '后台同步执行中断，稍后可安全重试。'
        job.finished_at = datetime.utcnow()
    code = job.error_code if job and job.status not in {'succeeded', 'cancelled'} else None
    if job and job.data_scope != 'activities' and connection.recovery_last_error_code:
        code = connection.recovery_last_error_code
    if code:
        state.failure_count += 1
        state.error_category = error_category(code)
        delay = min(360, max(30 if state.error_category == 'RATE_LIMIT' else 5, 5 * 2 ** min(state.failure_count, 6)))
        state.next_retry_at = datetime.utcnow() + timedelta(minutes=delay)
        if state.error_category == 'AUTH':
            connection.status = 'reauthentication_required'
    else:
        state.failure_count, state.error_category, state.next_retry_at = 0, None, None
    state.lease_token = state.lease_until = state.active_job_id = None
    db.commit()


class LeaseHeartbeat:
    def __init__(self, bind, lease):
        self.bind, self.lease, self.stop = bind, lease, Event()
        self.thread = Thread(target=self._run, daemon=True)

    def _run(self):
        while not self.stop.wait(30):
            try:
                with Session(self.bind) as db:
                    if not renew(db, self.lease):
                        return
            except Exception:
                return  # Expiry fences off the business transaction.

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=1)
