"""Smart Sync acceptance: synthetic facts, explicit isolated MySQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import Mock

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from tests.test_mcp_facts_v3_mysql import engine, sample
from planner_core.config import get_settings
from planner_core.database.models import ExternalAccountConnection, ExternalActivity, ExternalSyncJob, GarminSmartSyncState
from server.services import garmin_smart_sync_service as smart, garmin_sync_service as sync
from server.schemas.smart_sync import SmartSyncSettings
from server.integrations.activity_provider.mock import MockActivityProvider
from server.integrations.activity_provider.base import ProviderError
from server.integrations.activity_sync.pipeline import ActivitySyncPipeline


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setenv('GARMIN_SMART_SYNC_ENABLED', 'true')
    monkeypatch.setenv('GARMIN_SYNC_ROLLOUT_MODE', 'all')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def setup(sample, recovery=False):
    db, users, log, acts = sample
    uid = users[0].id
    smart.configure(db, uid, SmartSyncSettings(enabled=True, recovery_enabled=recovery))
    connection = db.get(ExternalAccountConnection, acts[0].connection_id)
    connection.last_successful_sync_at = None
    connection.recovery_last_successful_sync_at = None
    state = db.get(GarminSmartSyncState, connection.id)
    state.next_check_at = datetime.utcnow()-timedelta(seconds=1)
    db.commit()
    return db, uid, connection, state


@pytest.mark.parametrize('trigger', ['scheduled', 'login', 'home', 'mcp'])
def test_stale_enqueues_fresh_skips_and_repeated_calls_share_job(sample, trigger):
    db, uid, connection, state = setup(sample)
    connection.last_successful_sync_at = datetime.utcnow(); db.commit()
    assert smart.request_sync(db, uid, trigger=trigger, scope='activities').job_id is None
    connection.last_successful_sync_at = None
    state.next_check_at = datetime.utcnow()-timedelta(seconds=1); db.commit()
    first = smart.request_sync(db, uid, trigger=trigger, scope='activities')
    again = smart.request_sync(db, uid, trigger=trigger, scope='activities')
    assert first.status == 'QUEUED' and first.job_id == again.job_id
    assert db.get(ExternalSyncJob, first.job_id).data_scope == 'activities'


@pytest.mark.parametrize('policy', ['disabled', 'backoff', 'reauth', 'recent_attempt', 'recovery_not_enabled'])
def test_policies_prevent_unwanted_enqueues(sample, policy):
    db, uid, connection, state = setup(sample)
    scope = 'activities'
    if policy == 'disabled': connection.auto_sync_enabled = False
    if policy == 'backoff': state.next_retry_at = datetime.utcnow()+timedelta(hours=1)
    if policy == 'reauth': connection.status = 'reauthentication_required'
    if policy == 'recent_attempt': state.last_attempt_at = datetime.utcnow()
    if policy == 'recovery_not_enabled': scope = 'recovery'
    db.commit()
    assert smart.request_sync(db, uid, trigger='mcp', scope=scope).job_id is None


def test_three_concurrent_entrypoints_deduplicate_in_real_sessions(sample, engine):
    db, uid, connection, state = setup(sample, recovery=True)
    def request(trigger):
        with Session(engine) as other:
            return smart.request_sync(other, uid, trigger=trigger).job_id
    with ThreadPoolExecutor(max_workers=3) as pool:
        ids = list(pool.map(request, ['scheduled', 'login', 'mcp']))
    assert len(set(ids)) == 1 and ids[0] is not None
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(ExternalSyncJob).where(ExternalSyncJob.connection_id == connection.id)) == 1


def test_connection_lease_renewal_takeover_and_old_owner_fencing(sample, engine):
    db, uid, connection, state = setup(sample)
    job_id = smart.request_sync(db, uid, trigger='home').job_id
    lease = smart.acquire(db, job_id)
    assert lease and smart.renew(db, lease)
    with Session(engine) as other:
        assert smart.acquire(other, job_id) is None
    job = db.get(ExternalSyncJob, job_id); job.status = 'running'
    state = db.get(GarminSmartSyncState, connection.id)
    state.lease_until = datetime.utcnow()-timedelta(seconds=1)
    second = ExternalSyncJob(user_id=uid, connection_id=connection.id, sync_mode='incremental', status='queued')
    db.add(second); db.commit()
    next_lease = smart.acquire(db, second.id)
    assert next_lease and next_lease != lease
    assert not smart.lease_valid(db, lease) and not smart.renew(db, lease)
    assert db.get(ExternalSyncJob, job_id).status == 'failed'
    smart.release(db, lease, job_id)
    assert smart.lease_valid(db, next_lease)


def test_late_provider_cannot_commit_after_another_worker_takes_over(sample, engine, monkeypatch):
    db, uid, connection, state = setup(sample)
    started, resume = Event(), Event()
    provider = MockActivityProvider()
    def delayed_fetch(*_):
        started.set()
        assert resume.wait(10)
        return []
    provider.fetch_activities = delayed_fetch
    mock_provider(monkeypatch, provider)
    job_id = smart.request_sync(db, uid, trigger='home', scope='activities').job_id
    def execute():
        with Session(engine) as worker_db:
            return sync.run_sync_job(worker_db, job_id)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(execute)
        try:
            assert started.wait(10)
            db.expire_all()
            state.lease_until = datetime.utcnow()-timedelta(seconds=1)
            second = ExternalSyncJob(user_id=uid, connection_id=connection.id, sync_mode='incremental', status='queued')
            db.add(second); db.commit()
            next_lease = smart.acquire(db, second.id)
            assert next_lease
        finally:
            resume.set()
        assert not future.result(timeout=15).committed
    db.expire_all()
    assert db.get(ExternalSyncJob, job_id).error_code == 'WORKER_LEASE_EXPIRED'
    assert smart.lease_valid(db, next_lease)
    assert connection.last_successful_sync_at is None


def test_graceful_interruption_does_not_strand_running_job(sample):
    db, uid, connection, state = setup(sample)
    job_id = smart.request_sync(db, uid, trigger='home').job_id
    lease = smart.acquire(db, job_id)
    job = db.get(ExternalSyncJob, job_id)
    job.status = 'running'; db.commit()
    smart.release(db, lease, job_id)
    db.expire_all()
    assert job.status == 'failed' and job.error_code == 'WORKER_INTERRUPTED'
    assert state.lease_token is None and state.active_job_id is None
    assert state.next_retry_at is not None
    assert state.error_category == 'WORKER'


def mock_provider(monkeypatch, provider):
    monkeypatch.setattr(sync, '_provider_for_connection', lambda _: provider)
    monkeypatch.setattr(sync, 'decrypt_token_payload', lambda _: {})
    monkeypatch.setattr(sync, 'encrypt_token_payload', lambda _: 'synthetic-encrypted')


def test_existing_pipeline_import_is_idempotent_and_preserves_manual_rating(sample, engine, monkeypatch):
    db, uid, connection, state = setup(sample)
    provider = MockActivityProvider()
    provider.fetch_recovery = Mock(side_effect=AssertionError('Activity-only request must not query recovery'))
    mock_provider(monkeypatch, provider)
    first = smart.request_sync(db, uid, trigger='home', scope='activities')
    pipeline = ActivitySyncPipeline(snapshot_session_factory=sessionmaker(engine))
    outcome = pipeline.run_job(db, first.job_id)
    assert outcome.sync_outcome.committed
    assert outcome.runner_state_snapshot is not None
    provider.fetch_recovery.assert_not_called()
    db.expire_all()
    imported = db.scalar(select(ExternalActivity).where(ExternalActivity.user_id == uid,
        ExternalActivity.external_activity_id.like('mock-%')))
    assert imported is not None
    from planner_core.database.models import WorkoutLog
    log = db.get(WorkoutLog, imported.workout_log_id)
    log.rpe = 7; log.review_note = 'synthetic manual note'
    log.field_sources_json = {**(log.field_sources_json or {}), 'rpe': 'manual', 'review_note': 'manual'}
    state.last_attempt_at = None; db.commit()
    second = smart.request_sync(db, uid, trigger='manual', scope='activities')
    pipeline.run_job(db, second.job_id)
    db.expire_all()
    assert log.rpe == 7 and log.review_note == 'synthetic manual note'
    assert db.scalar(select(func.count()).select_from(ExternalActivity).where(ExternalActivity.user_id == uid,
        ExternalActivity.external_activity_id == imported.external_activity_id)) == 1


@pytest.mark.parametrize('code,category', [('REAUTHENTICATION_REQUIRED','AUTH'), ('RATE_LIMITED','RATE_LIMIT'),
    ('NETWORK_TIMEOUT','NETWORK'), ('ACTIVITY_PARSE_FAILED','PARSING'), ('SYNC_COMMIT_FAILED','DATABASE'), ('INVALID_RESPONSE','PROVIDER')])
def test_failure_categories_and_backoff_do_not_remove_stored_facts(sample, monkeypatch, code, category):
    db, uid, connection, state = setup(sample)
    provider = MockActivityProvider()
    provider.fetch_activities = Mock(side_effect=ProviderError(code, 'Synthetic provider failure'))
    mock_provider(monkeypatch, provider)
    result = smart.request_sync(db, uid, trigger='mcp')
    outcome = sync.run_sync_job(db, result.job_id)
    assert not outcome.committed
    db.expire_all()
    assert db.get(GarminSmartSyncState, connection.id).error_category == category
    assert smart.request_sync(db, uid, trigger='mcp').job_id is None
    from server.mcp.facts_v2 import read_training
    assert read_training(db, uid).items  # Existing facts survive all Provider failures.


def test_recovery_only_preserves_activity_freshness_and_nulls(sample, monkeypatch):
    db, uid, connection, state = setup(sample, recovery=True)
    provider = MockActivityProvider()
    provider.fetch_activities = Mock(side_effect=AssertionError('Recovery request must not fetch activities'))
    mock_provider(monkeypatch, provider)
    job = smart.request_sync(db, uid, trigger='mcp', scope='recovery')
    assert sync.run_sync_job(db, job.job_id).committed
    db.expire_all()
    assert connection.last_successful_sync_at is None
    assert connection.recovery_last_successful_sync_at is not None
    provider.fetch_activities.assert_not_called()


def test_mcp_scope_checks_precede_sync_and_training_cannot_sync_recovery(sample, engine, monkeypatch):
    from server.mcp.adapters import McpToolAdapter
    from server.mcp.context import McpExecutionContext, McpRequestIdentity
    db, uid, connection, state = setup(sample, recovery=True)
    factory = sessionmaker(engine)
    denied_factory = Mock(side_effect=AssertionError('No DB work before recovery consent'))
    denied = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(uid), session_factory=denied_factory))
    assert denied.get_recovery_trend(days=14).error.code.value == 'INSUFFICIENT_PERMISSION'
    denied_factory.assert_not_called()
    allowed = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(uid), session_factory=factory))
    result = allowed.get_recent_training(days=7, cursor='first')
    assert result.status == 'SUCCEEDED' and result.freshness.status == 'QUEUED'
    with factory() as check:
        assert check.get(ExternalSyncJob, result.freshness.job_id).data_scope == 'activities'


def test_recovery_14_and_28_day_queries_share_permission_and_sync_scope(sample, engine):
    from server.mcp.adapters import McpToolAdapter
    from server.mcp.context import McpExecutionContext, McpRequestIdentity
    db, uid, connection, state = setup(sample, recovery=True)
    adapter = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(uid,
        frozenset({'mcp:read', 'mcp:recovery:read'})), session_factory=sessionmaker(engine)))
    first = adapter.get_recovery_trend(days=14)
    second = adapter.get_recovery_trend(days=28)
    assert first.status == second.status == 'SUCCEEDED'
    assert first.freshness.job_id == second.freshness.job_id
    assert first.freshness.scope == second.freshness.scope == 'recovery'


def test_sync_check_failure_cannot_fail_existing_mcp_read(sample, engine, monkeypatch):
    from server.mcp.adapters import McpToolAdapter
    from server.mcp.context import McpExecutionContext, McpRequestIdentity
    db, uid, connection, state = setup(sample)
    monkeypatch.setattr(smart, 'request_sync', Mock(side_effect=RuntimeError('synthetic coordinator outage')))
    adapter = McpToolAdapter(McpExecutionContext(identity_provider=lambda: McpRequestIdentity(uid), session_factory=sessionmaker(engine)))
    result = adapter.get_recent_training(days=7, cursor='first')
    assert result.status == 'SUCCEEDED' and result.data.items
    assert result.freshness.status == 'CHECK_UNAVAILABLE'


@pytest.mark.parametrize('revoke', ['automatic', 'recovery', 'user'])
def test_queued_work_rechecks_current_consent_before_provider_access(sample, revoke):
    db, uid, connection, state = setup(sample, recovery=True)
    result = smart.request_sync(db, uid, trigger='mcp', scope='recovery')
    if revoke == 'automatic': connection.auto_sync_enabled = False
    if revoke == 'recovery': state.recovery_enabled = False
    if revoke == 'user': sample[1][0].status = 'disabled'
    db.commit()
    assert smart.acquire(db, result.job_id) is None
    assert db.get(ExternalSyncJob, result.job_id).status == 'cancelled'


def test_login_queues_only_database_work_and_failure_does_not_fail_authentication(sample, monkeypatch):
    from server.services import auth_service
    from server.schemas.auth import UserLogin
    db, uid, connection, state = setup(sample)
    user = sample[1][0]
    user.password_hash = auth_service.hash_password('synthetic-password-only')
    db.commit()
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-test-key-not-for-deployment')
    get_settings.cache_clear()
    provider = Mock(side_effect=AssertionError('Login cannot contact Garmin'))
    monkeypatch.setattr(sync, '_provider_for_connection', provider)
    result = auth_service.authenticate_user(db, UserLogin(username=user.username, password='synthetic-password-only'))
    assert result.access_token
    provider.assert_not_called()
    with Session(db.get_bind()) as check:
        job = check.scalar(select(ExternalSyncJob).where(ExternalSyncJob.connection_id == connection.id))
        assert job.trigger_source == 'login' and job.status == 'queued'
    monkeypatch.setattr(smart, 'request_sync', Mock(side_effect=RuntimeError('synthetic coordinator outage')))
    assert auth_service.authenticate_user(db, UserLogin(username=user.username, password='synthetic-password-only')).access_token


def test_scheduler_stagger_and_expired_worker_recovery(sample, engine):
    from scripts.garmin_smart_sync_worker import tick
    db, uid, connection, state = setup(sample)
    job_id = smart.request_sync(db, uid, trigger='home').job_id
    lease = smart.acquire(db, job_id)
    db.get(ExternalSyncJob, job_id).status = 'running'
    state.lease_until = datetime.utcnow()-timedelta(seconds=1); db.commit()
    tick(sessionmaker(engine), Mock())
    db.expire_all()
    assert db.get(ExternalSyncJob, job_id).error_code == 'WORKER_LEASE_EXPIRED'
    assert not smart.lease_valid(db, lease)
    assert state.next_retry_at > datetime.utcnow()


def test_user_isolation_and_frequency_validation(sample):
    from pydantic import ValidationError
    db, uid, connection, state = setup(sample)
    other = sample[1][1].id
    assert smart.request_sync(db, other, trigger='home').job_id is None
    for value in [0, 1, 29, 1441]:
        with pytest.raises(ValidationError): SmartSyncSettings(enabled=True, interval_minutes=value)


def test_migration_repeated_and_partial_upgrade_preserves_legacy_jobs(sample):
    from scripts.upgrade_garmin_smart_sync import upgrade
    db, users, log, acts = sample
    job = ExternalSyncJob(user_id=users[0].id, connection_id=acts[0].connection_id, sync_mode='recent_7d')
    db.add(job); db.commit()
    job_id = job.id
    # Dedicated test schema only; model instances are not used until restored.
    db.execute(text('ALTER TABLE external_sync_job DROP COLUMN trigger_source'))
    db.commit()
    with db.get_bind().begin() as connection:
        upgrade(connection); upgrade(connection)
    db.expire_all()
    assert db.get(ExternalSyncJob, job_id).trigger_source == 'manual'
    assert db.get(ExternalSyncJob, job_id).data_scope == 'all'
