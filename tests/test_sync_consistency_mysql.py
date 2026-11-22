"""Scope receipts and watermarks: real isolated MySQL, synthetic Provider only."""
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from tests.test_garmin_smart_sync_mysql import engine, sample, enabled, setup, mock_provider
from planner_core.database.models import ExternalSyncJob
from server.integrations.activity_provider.mock import MockActivityProvider
from server.integrations.activity_provider.base import ProviderError
from server.services import garmin_smart_sync_service as smart, garmin_sync_service as sync


def test_recovery_job_is_not_training_job_and_terminal_receipt_survives(sample, monkeypatch):
    db, uid, connection, state = setup(sample, recovery=True)
    provider = MockActivityProvider()
    provider.fetch_activities = Mock(side_effect=AssertionError('No activity fetch'))
    mock_provider(monkeypatch, provider)
    queued = smart.request_sync(db, uid, trigger='mcp', scope='recovery')
    training = smart.status(db, uid, 'activities')
    assert training.job_id is None and training.last_job is None
    assert training.status == 'WAITING_FOR_OTHER_SCOPE'
    assert training.blocking_job.job_id == queued.job_id
    sync.run_sync_job(db, queued.job_id)
    receipt = smart.status(db, uid, 'recovery')
    assert receipt.job_id is None and receipt.last_job.job_id == queued.job_id
    assert receipt.last_job.status == 'succeeded' and receipt.last_job.finished_at
    assert receipt.last_success_at and connection.last_successful_sync_at is None
    # Recovery just completed: it must not suppress the stale training scope.
    training = smart.request_sync(db, uid, trigger='mcp', scope='activities')
    assert training.status == 'QUEUED' and training.job_id != queued.job_id
    provider.fetch_activities.assert_not_called()


def test_scheduler_fresh_check_anchors_to_watermark_not_now(sample):
    db, uid, connection, state = setup(sample)
    now = datetime.utcnow()
    state.interval_minutes = 1440
    connection.last_successful_sync_at = now-timedelta(hours=23)
    state.next_check_at = now-timedelta(seconds=1)
    db.commit()
    result = smart.request_sync(db, uid, trigger='scheduled', scope='activities', now=now)
    assert result.job_id is None
    assert state.next_check_at < now+timedelta(hours=2)
    later = smart.request_sync(db, uid, trigger='scheduled', scope='activities', now=now+timedelta(hours=2))
    assert later.job_id and later.last_job.scope == 'activities'


def test_unrelated_active_scope_does_not_consume_due_schedule(sample):
    db, uid, connection, state = setup(sample, recovery=True)
    db.refresh(state)
    due = state.next_check_at
    smart.request_sync(db, uid, trigger='mcp', scope='recovery')
    training = smart.request_sync(db, uid, trigger='scheduled', scope='activities')
    assert training.job_id is None and training.blocking_job.scope == 'recovery'
    assert state.next_check_at == due


@pytest.mark.parametrize('scope', ['recovery', 'all'])
def test_recovery_failure_never_claims_complete_success(sample, monkeypatch, scope):
    db, uid, connection, state = setup(sample, recovery=True)
    old = datetime.utcnow()-timedelta(days=2)
    connection.recovery_last_successful_sync_at = old
    connection.last_error_code = 'SYNC_FAILED'
    db.commit()
    db.refresh(connection)
    old = connection.recovery_last_successful_sync_at
    provider = MockActivityProvider()
    provider.fetch_activities = Mock(return_value=[])
    provider.fetch_recovery = Mock(side_effect=ProviderError('NETWORK_TIMEOUT', 'synthetic failure'))
    mock_provider(monkeypatch, provider)
    queued = smart.request_sync(db, uid, trigger='mcp', scope=scope)
    outcome = sync.run_sync_job(db, queued.job_id)
    db.expire_all()
    job = db.get(ExternalSyncJob, queued.job_id)
    assert job.status == ('failed' if scope == 'recovery' else 'partially_succeeded')
    assert connection.recovery_last_successful_sync_at == old
    assert connection.recovery_last_error_code == 'NETWORK_TIMEOUT'
    receipt = smart.status(db, uid, scope)
    assert receipt.last_job.finished_at and receipt.last_job.error_category
    if scope == 'all':
        assert outcome.committed and connection.last_successful_sync_at
        assert connection.last_error_code is None
        assert receipt.data_freshness_by_scope['activities'] == 'FRESH'
        assert receipt.data_freshness_by_scope['recovery'] != 'FRESH'
    else:
        assert not outcome.committed and connection.last_successful_sync_at is None
        provider.fetch_activities.assert_not_called()


def test_failed_receipt_is_scoped_private_and_retryable(sample, monkeypatch):
    db, uid, connection, state = setup(sample)
    provider = MockActivityProvider()
    provider.fetch_activities = Mock(side_effect=ProviderError('NETWORK_TIMEOUT', 'PRIVATE_SENTINEL'))
    mock_provider(monkeypatch, provider)
    queued = smart.request_sync(db, uid, trigger='mcp', scope='activities')
    sync.run_sync_job(db, queued.job_id)
    result = smart.status(db, uid)
    assert result.last_job.job_id == queued.job_id and result.last_job.outcome == 'FAILED'
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()
    other = smart.status(db, sample[1][1].id)
    assert other.last_job is None and other.blocking_job is None
    state.next_retry_at = datetime.utcnow()-timedelta(seconds=1)
    db.commit()
    retried = smart.request_sync(db, uid, trigger='manual', scope='activities')
    assert retried.job_id and retried.job_id != queued.job_id


def test_pending_activity_is_visible_as_gap_not_fabricated_workout(sample):
    from server.mcp.facts_v2 import read_training
    db, users, log, acts = sample
    acts[0].resolution_status = 'needs_review'
    acts[0].processing_status = 'pending'
    db.commit()
    result = read_training(db, users[0].id, days=7)
    assert result.summary.unresolved_activity_count >= 1
    assert result.summary.total_sessions == 1
    assert 'UNRESOLVED_ACTIVITIES' in [issue.code for issue in result.fact_issues]
    assert result.data_status == 'PARTIAL'


def test_incremental_multiple_activities_without_plan_are_recomputed_idempotently(sample, monkeypatch):
    from copy import deepcopy
    from server.services.training_load_service import get_recent_training_read
    db, uid, connection, state = setup(sample)
    provider = MockActivityProvider()
    first = provider.fetch_activities(datetime.utcnow()-timedelta(days=2), datetime.utcnow())[0]
    second = deepcopy(first)
    second.external_activity_id += '-second'
    second.start_time_local = first.start_time_local+timedelta(hours=1)
    second.distance_m = first.distance_m/2
    provider.fetch_activity_summary = None
    mock_provider(monkeypatch, provider)
    for supplied in ([first], [first, second], [first, second]):
        provider.fetch_activities = Mock(return_value=supplied)
        job = smart.request_sync(db, uid, trigger='manual', scope='activities')
        assert sync.run_sync_job(db, job.job_id).committed
        db.expire_all()
        result = get_recent_training_read(db, user_id=uid, days=1, limit=20, as_of_date=first.start_time_local.date())
        assert result.total_sessions == 1 and result.unplanned_sessions == 1
        expected = float(first.distance_m)*(1 if len(supplied) == 1 else 1.5)/1000
        assert result.total_distance_km == pytest.approx(round(expected, 2))
    assert smart.status(db, uid).last_job.outcome == 'SUCCEEDED_NO_ACTIVITY_CHANGES'


def test_partial_activity_commit_keeps_complete_watermark(sample, monkeypatch):
    from copy import deepcopy
    db, uid, connection, state = setup(sample)
    old = (datetime.utcnow()-timedelta(days=2)).replace(microsecond=0)
    connection.last_successful_sync_at = old
    db.commit()
    provider = MockActivityProvider()
    first = provider.fetch_activities(datetime.utcnow()-timedelta(days=2), datetime.utcnow())[0]
    second = deepcopy(first)
    second.external_activity_id += '-broken'
    provider.fetch_activities = Mock(return_value=[first, second])
    provider.fetch_activity_summary = None
    original = sync._process_provider_activity
    def process(db, job, activity, *args, **kwargs):
        if activity.external_activity_id.endswith('-broken'):
            raise ValueError('synthetic invalid activity')
        return original(db, job, activity, *args, **kwargs)
    monkeypatch.setattr(sync, '_process_provider_activity', process)
    mock_provider(monkeypatch, provider)
    job = smart.request_sync(db, uid, trigger='manual', scope='activities')
    result = sync.run_sync_job(db, job.job_id)
    db.expire_all()
    assert result.committed and result.final_status == 'partially_succeeded'
    assert connection.last_successful_sync_at == old
    receipt = smart.status(db, uid)
    assert receipt.last_job.failed_count == 1
    assert receipt.data_freshness != 'FRESH'


def test_runner_reports_both_scope_watermarks_without_syncing(sample):
    from server.agent.tools.dependencies import CoachAgentToolDependencies
    from server.agent.tools.runner_state_tools import GetRunnerStateTool
    from server.agent.tools.schemas import EmptyToolInput
    from server.mcp.adapters import McpToolAdapter
    from tests.test_agent_runner_state_tools import context
    db, uid, connection, state = setup(sample, recovery=True)
    connection.last_successful_sync_at = (datetime.utcnow()-timedelta(days=2)).replace(microsecond=0)
    connection.recovery_last_successful_sync_at = datetime.utcnow().replace(microsecond=0)
    db.commit()
    output = GetRunnerStateTool(CoachAgentToolDependencies.from_session(db)).execute(EmptyToolInput(), context(uid))
    assert output.sync_provenance.last_success_by_scope['activities'] < output.sync_provenance.last_success_by_scope['recovery']
    assert output.data_status.value != 'AVAILABLE'
    assert 'SYNC_FACTS_INCOMPLETE' in [notice.code for notice in output.limitations]
    mcp = McpToolAdapter._runner_state(output.model_dump(mode='json'))
    assert mcp.assessment_status != 'ASSESSED' and mcp.sync_provenance
    assert 'hrv_value' not in mcp.metrics
    assert db.scalar(select(ExternalSyncJob).where(ExternalSyncJob.user_id == uid)) is None
