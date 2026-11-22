"""Read/write regression on an explicit isolated MySQL using synthetic facts."""
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import delete, func, select
from tests.test_mcp_facts_v3_mysql import engine, sample, DAY
from planner_core.database.models import ExternalActivityLap, ExternalActivityRaw, ExternalAccountConnection, ExternalSyncJob, PlannedWorkout
from planner_core.config import get_settings
from planner_core.enums import WorkoutMainTypeNormalized
from server.integrations.activity_provider.base import ProviderActivity, ProviderLap
from server.services.garmin_sync_service import _replace_laps
from server.services import garmin_smart_sync_service as smart
from server.mcp.facts_v2 import read_training_detail, read_training
from server.services.training_load_service import get_recent_training_read


def candidate(activity, *, count=4, summary=False, hr=True):
    return ProviderActivity(external_activity_id=activity.external_activity_id, activity_name=None,
        activity_type='outdoor_running', activity_subtype=None, start_time_local=activity.start_time_local,
        distance_m=Decimal('2000'), duration_seconds=480, timer_time_seconds=480,
        laps=[ProviderLap(lap_index=i+1, distance_m=Decimal(2000)/count, duration_seconds=480//count,
            timer_time_seconds=480//count, start_offset_seconds=None if summary else i*(480//count),
            average_heart_rate_bpm=150 if hr else None,
            lap_type='INTERVAL_ACTIVE' if summary else None, workout_step_type='ACTIVE',
            segment_role='summary' if summary else 'unknown',
            classification_source='garmin_summary_rollup' if summary else 'garmin_lap_dto') for i in range(count)])


def initialize(db, activity):
    db.execute(delete(ExternalActivityLap).where(ExternalActivityLap.external_activity_id == activity.id))
    activity.distance_m=2000; activity.duration_seconds=480; activity.timer_time_seconds=480
    _replace_laps(db, activity, candidate(activity))
    db.commit()


def stored(db, activity):
    return list(db.scalars(select(ExternalActivityLap).where(ExternalActivityLap.external_activity_id == activity.id)
        .order_by(ExternalActivityLap.lap_index)))


def snapshots(db, activity):
    rows = db.scalars(select(ExternalActivityRaw).where(ExternalActivityRaw.user_id == activity.user_id,
        ExternalActivityRaw.external_activity_id == activity.external_activity_id)).all()
    return [row for row in rows if (row.raw_payload_json or {}).get('kind') == 'lap_snapshot_v1']


def test_summary_does_not_overwrite_existing_laps_and_private_versions_are_retained(sample):
    db, users, log, acts = sample
    activity=acts[1]; initialize(db,activity)
    ids=[row.id for row in stored(db,activity)]
    _replace_laps(db,activity,candidate(activity,summary=True))
    db.commit()
    assert [row.id for row in stored(db,activity)] == ids
    assert len(snapshots(db,activity)) == 2
    detail=read_training_detail(db,users[0].id,f'external_activity:{activity.id}')
    assert detail.segment_storage['decision']=='PRESERVED'
    assert detail.segment_storage['requires_review']
    assert any(issue.code=='LAP_DOWNGRADE_REJECTED' for issue in detail.fact_issues)
    assert detail.raw_segments_complete and detail.normalized_structure_complete
    assert detail.activity_classification['confirmation_status']=='NOT_USER_CONFIRMED'
    assert 'current_digest' not in detail.model_dump_json() and 'lap_snapshot_v1' not in detail.model_dump_json()


def test_fewer_laps_and_lost_optional_metrics_are_rejected(sample):
    db, users, log, acts=sample
    activity=acts[1]; initialize(db,activity)
    for proposed in [candidate(activity,count=2),candidate(activity,hr=False)]:
        _replace_laps(db,activity,proposed); db.commit()
        rows=stored(db,activity)
        assert len(rows)==4 and all(row.average_heart_rate_bpm==150 for row in rows)
        assert activity.field_sources_json['lap_sync']['reason']=='DETAIL_COVERAGE_REGRESSION'


def test_same_content_is_idempotent_across_database_decimal_scales(sample):
    db, users, log, acts=sample
    activity=acts[1]; initialize(db,activity)
    ids=[row.id for row in stored(db,activity)]
    version=activity.field_sources_json['lap_sync']['version']
    for _ in range(2):
        db.expire_all()
        _replace_laps(db,activity,candidate(activity)); db.commit()
        assert [row.id for row in stored(db,activity)]==ids
        assert activity.field_sources_json['lap_sync']['version']==version
    assert len(snapshots(db,activity))==1


def test_failed_transaction_does_not_publish_new_laps_or_version_snapshots(sample):
    db, users, log, acts=sample
    activity=acts[1]; initialize(db,activity)
    original=[row.id for row in stored(db,activity)]
    next_value=candidate(activity)
    next_value.laps[0].average_heart_rate_bpm=151
    _replace_laps(db,activity,next_value); db.flush()
    db.rollback(); db.expire_all()
    assert [row.id for row in stored(db,activity)]==original
    assert len(snapshots(db,activity))==1


def test_empty_result_preserves_existing_detail_and_summary_upgrades_to_detail(sample):
    db, users, log, acts=sample
    activity=acts[0]
    activity.distance_m=2000;activity.duration_seconds=480;activity.timer_time_seconds=480
    _replace_laps(db,activity,candidate(activity,summary=True));db.commit()
    assert not read_training_detail(db,users[0].id,f'external_activity:{activity.id}').normalized_structure_complete
    _replace_laps(db,activity,candidate(activity));db.commit()
    ids=[row.id for row in stored(db,activity)]
    empty=candidate(activity);empty.laps=[]
    _replace_laps(db,activity,empty);db.commit()
    assert [row.id for row in stored(db,activity)]==ids


def test_planned_quality_is_not_counted_as_observed_quality_with_unknown_actual_type(sample):
    db,users,log,acts=sample
    plan=db.get(PlannedWorkout,log.planned_workout_id)
    plan.main_type_normalized=WorkoutMainTypeNormalized.interval_speed
    log.workout_type='unknown';log.source_type='garmin_sync';log.field_sources_json={};db.commit()
    recent=get_recent_training_read(db,user_id=users[0].id,days=7,limit=20,as_of_date=DAY)
    mcp=read_training(db,users[0].id,days=7)
    assert recent.completed_key_sessions==mcp.summary.completed_key_sessions==0
    assert recent.classification_coverage==mcp.summary.classification_coverage==0
    assert recent.key_session_count_status==mcp.summary.key_session_count_status=='UNKNOWN'
    log.workout_type='interval_speed';log.field_sources_json={'workout_type':'manual'};db.commit()
    recent=get_recent_training_read(db,user_id=users[0].id,days=7,limit=20,as_of_date=DAY)
    assert recent.completed_key_sessions==1 and recent.key_session_count_status=='COMPLETE'


def test_disabled_sync_can_independently_report_stale_data_without_enqueuing(sample, monkeypatch):
    monkeypatch.setenv('GARMIN_SMART_SYNC_ENABLED','true');get_settings.cache_clear()
    try:
        db,users,log,acts=sample
        connection=db.get(ExternalAccountConnection,acts[0].connection_id)
        connection.auto_sync_enabled=False
        connection.last_successful_sync_at=datetime.utcnow()-timedelta(days=1)
        db.commit()
        result=smart.request_sync(db,users[0].id,trigger='mcp',scope='activities')
        assert result.status==result.sync_status=='AUTO_SYNC_DISABLED'
        assert result.data_freshness=='STALE' and result.data_freshness_by_scope=={'activities':'STALE'}
        assert db.scalar(select(func.count()).select_from(ExternalSyncJob).where(ExternalSyncJob.user_id==users[0].id))==0
        assert result.model_dump(mode='json')['last_success_at'].endswith('+00:00')
    finally:
        get_settings.cache_clear()


def test_cross_user_cannot_read_private_versions_or_selected_detail(sample):
    from server.mcp.errors import McpSafeError
    import pytest
    db,users,log,acts=sample
    initialize(db,acts[1])
    with pytest.raises(McpSafeError):read_training_detail(db,users[1].id,f'external_activity:{acts[1].id}')


def test_coach_receives_staleness_without_submitting_a_sync_job(sample, engine, monkeypatch):
    from sqlalchemy import event
    from datetime import timezone
    from uuid import uuid4
    from server.agent.tools.training_tools import GetRecentTrainingTool
    from server.agent.tools.schemas import RecentTrainingInput
    from server.agent.tools.dependencies import CoachAgentToolDependencies
    from server.agent.schemas import AgentContext
    from server.agent.enums import AgentIntent
    monkeypatch.setenv('GARMIN_SMART_SYNC_ENABLED','true');get_settings.cache_clear()
    db,users,log,acts=sample
    connection=db.get(ExternalAccountConnection,acts[0].connection_id)
    connection.auto_sync_enabled=False
    connection.last_successful_sync_at=datetime.utcnow()-timedelta(days=1);db.commit()
    def forbid_writes(_conn,_cursor,statement,*_args):
        assert statement.lstrip().split()[0].upper() not in {'INSERT','UPDATE','DELETE','ALTER','CREATE','DROP'}
    event.listen(engine,'before_cursor_execute',forbid_writes)
    try:
        result=GetRecentTrainingTool(CoachAgentToolDependencies.from_session(db)).execute(RecentTrainingInput(days=7),
            AgentContext(request_id=uuid4(),user_id=users[0].id,intent=AgentIntent.PERSONAL_TRAINING_ANALYSIS,
                current_time=datetime.combine(DAY,datetime.min.time(),tzinfo=timezone.utc),timezone='Asia/Shanghai'))
        assert result.freshness.data_freshness=='STALE'
        assert result.freshness.sync_status=='AUTO_SYNC_DISABLED'
        assert result.freshness.facts_read_at is not None
    finally:
        event.remove(engine,'before_cursor_execute',forbid_writes)
        get_settings.cache_clear()
