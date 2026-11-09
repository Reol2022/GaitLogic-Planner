"""Real MySQL, synthetic fixtures only. Explicit local test URL is mandatory."""
import asyncio
import os
from datetime import date,datetime,timedelta
from uuid import uuid4

import pytest
from mcp.client import Client
from sqlalchemy import create_engine,delete,event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from planner_core.database.models import (Base,UserAccount,WorkoutLog,TrainingCycle,TrainingBlock,PlannedWorkout,
    ExternalAccountConnection,ExternalActivity,ExternalActivityLap,WorkoutLogExternalActivity,DailyRecoveryCheckin)
from planner_core.enums import WorkoutMainTypeNormalized,WorkoutStatusNormalized
from server.mcp.facts_v2 import read_training_detail,read_recovery,read_training
from server.mcp.context import McpExecutionContext,McpRequestIdentity
from server.mcp.server import create_mcp_server
from server.mcp.errors import McpSafeError,McpErrorCode
from server.services.training_load_service import get_recent_training_read
from server.services.runner_state_service import RunnerStateService

DAY=date(2026,7,21)


@pytest.fixture(scope='module')
def engine():
    raw=os.environ.get('GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL')
    if not raw:pytest.skip('Explicit isolated MySQL URL required')
    url=make_url(raw)
    if url.get_backend_name()!='mysql' or url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith('gaitlogic_test_'):
        pytest.fail('Refusing non-local or non-test database')
    value=create_engine(url)
    Base.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def sample(engine,monkeypatch):
    from server.mcp import facts_v2
    monkeypatch.setattr(facts_v2,'local_today',lambda:DAY)
    db=Session(engine,expire_on_commit=False)
    users=[UserAccount(username='synth-facts3-'+uuid4().hex[:16],password_hash='not-a-login',status='active') for _ in range(2)]
    db.add_all(users);db.flush()
    cycle=TrainingCycle(user_id=users[0].id,name='Synthetic cycle');db.add(cycle);db.flush()
    block=TrainingBlock(user_id=users[0].id,cycle_id=cycle.id,block_name='Synthetic week',sort_order=1);db.add(block);db.flush()
    plan=PlannedWorkout(user_id=users[0].id,cycle_id=cycle.id,block_id=block.id,planned_content='Synthetic rest label',
        workout_date=DAY-timedelta(days=8),sort_order=1,main_type_normalized=WorkoutMainTypeNormalized.rest)
    db.add(plan);db.flush()
    log=WorkoutLog(user_id=users[0].id,planned_workout_id=plan.id,activity_date=DAY,workout_type='rest',source_type='manual',
        status_normalized=WorkoutStatusNormalized.completed_normal,actual_distance_km=18.5,actual_duration_seconds=4500,
        field_sources_json={'actual_distance_km':'garmin','actual_duration_seconds':'garmin'},review_note='PRIVATE_SENTINEL')
    db.add(log);db.flush()
    connections=[ExternalAccountConnection(user_id=u.id,provider='garmin',encrypted_token_payload='PRIVATE_SENTINEL') for u in users]
    db.add_all(connections);db.flush()
    acts=[]
    for index,distance in enumerate([2000,15000,1500,1000]):
        owner=1 if index==3 else 0
        activity=ExternalActivity(user_id=users[owner].id,connection_id=connections[owner].id,provider='garmin',
            external_activity_id='synthetic-'+uuid4().hex,connector_version='synthetic',activity_name='PRIVATE_SENTINEL',activity_type='running',
            start_time_local=datetime(2026,7,21,6+index),activity_date=DAY,distance_m=distance,duration_seconds=3300 if index==1 else 600,
            timer_time_seconds=3300 if index==1 else 600,average_heart_rate_bpm=150,max_heart_rate_bpm=172,
            average_cadence_spm=180,average_stride_length_m=1.4,average_ground_contact_time_ms=205,average_running_power_w=310,
            elevation_gain_m=20,field_sources_json={'max_heart_rate_bpm':'garmin','secret':'PRIVATE_SENTINEL'})
        db.add(activity);db.flush();acts.append(activity)
        if index<3:
            db.add(WorkoutLogExternalActivity(user_id=users[0].id,workout_log_id=log.id,external_activity_id=activity.id))
    for index in range(1,3):
        db.add(ExternalActivityLap(external_activity_id=acts[1].id,lap_index=index,distance_m=500 if index==1 else 1500,
            duration_seconds=110 if index==1 else 330,average_heart_rate_bpm=150+index,max_heart_rate_bpm=160+index,average_cadence_spm=180))
    db.add(DailyRecoveryCheckin(user_id=users[0].id,checkin_date=DAY,hrv_value=54,hrv_metric='MS',hrv_source='garmin',
        average_stress=24,muscle_soreness=2,device_data_status='failed',notes='PRIVATE_SENTINEL'))
    db.commit()
    try:yield db,users,log,acts
    finally:
        db.rollback()
        db.execute(delete(UserAccount).where(UserAccount.id.in_([u.id for u in users])))
        db.commit();db.close()


def test_aggregate_is_not_a_race_and_explicit_selection_never_concatenates(sample):
    db,users,log,acts=sample
    ref=f'workout_log:{log.id}'
    result=read_training_detail(db,users[0].id,ref)
    assert result.record.distance_km==18.5 and result.record.source=='MANUAL'
    assert result.record.origin_source=='GARMIN'
    assert result.selection_required and result.selected_activity is None and result.segments==[]
    assert result.linked_activity_count==3
    race=read_training_detail(db,users[0].id,ref,f'external_activity:{acts[1].id}')
    assert race.record.distance_km==18.5 and race.selected_activity.distance_km==15
    assert race.selected_activity.max_heart_rate_bpm==172 and race.selected_activity.average_stride_length_m==1.4
    assert [lap.average_heart_rate_bpm for lap in race.segments]==[151,152]
    assert {lap.activity_ref for lap in race.segments}=={f'external_activity:{acts[1].id}'}
    assert race.segments[0].distance_m==500  # not relabelled as a kilometre split
    assert 'PRIVATE_SENTINEL' not in race.model_dump_json()
    assert race.segments_complete and race.segments_available
    assert race.segment_distance_consistent is False
    assert race.fact_issues[0].code=='LAP_ACTIVITY_DISTANCE_MISMATCH'


def test_direct_activity_and_wrong_user_or_wrong_link(sample):
    db,users,log,acts=sample
    direct=read_training_detail(db,users[0].id,f'external_activity:{acts[1].id}')
    assert direct.record is None and direct.selected_activity.distance_km==15
    for ref,selected,uid in [(f'workout_log:{log.id}',None,users[1].id),
        (f'external_activity:{acts[1].id}',None,users[1].id),
        (f'workout_log:{log.id}',f'external_activity:{acts[3].id}',users[0].id)]:
        with pytest.raises(McpSafeError) as exc:read_training_detail(db,uid,ref,selected)
        assert exc.value.code==McpErrorCode.RESOURCE_NOT_FOUND


def test_lap_truncation_and_missing_data_are_explicit(sample):
    db,users,log,acts=sample
    db.add_all([ExternalActivityLap(external_activity_id=acts[1].id,lap_index=n) for n in range(3,104)])
    db.commit()
    result=read_training_detail(db,users[0].id,f'external_activity:{acts[1].id}')
    assert len(result.segments)==100 and not result.segments_complete
    empty=read_training_detail(db,users[0].id,f'external_activity:{acts[0].id}')
    assert not empty.segments_available and empty.selected_activity.moving_time_seconds is None
    assert 'moving_time_seconds' in empty.selected_activity.missing_fields


def test_distance_conflict_is_local_and_not_overwritten(sample):
    db,users,log,acts=sample
    log.actual_distance_km=22;db.commit()
    result=read_training_detail(db,users[0].id,f'workout_log:{log.id}')
    assert result.fact_issues[0].code=='LOG_ACTIVITY_DISTANCE_MISMATCH'
    assert result.record.distance_km==22 and result.activities[1].distance_km==15


def test_many_activities_are_bounded_but_selection_can_target_hidden_same_user_activity(sample):
    db,users,log,acts=sample
    for n in range(20):
        activity=ExternalActivity(user_id=users[0].id,connection_id=acts[0].connection_id,provider='garmin',
            external_activity_id='synthetic-'+uuid4().hex,connector_version='synthetic',activity_type='running',
            start_time_local=datetime(2026,7,21,12),activity_date=DAY,workout_log_id=log.id)
        db.add(activity)
    db.commit()
    result=read_training_detail(db,users[0].id,f'workout_log:{log.id}')
    assert result.linked_activity_count==23 and len(result.activities)==20 and not result.activities_complete
    selected=read_training_detail(db,users[0].id,f'workout_log:{log.id}',f'external_activity:{activity.id}')
    assert selected.selected_activity.activity_ref==f'external_activity:{activity.id}'
    # Same-user but unrelated activity cannot be silently attached to another log.
    other=WorkoutLog(user_id=users[0].id,activity_date=DAY,source_type='manual',is_unplanned=True,
        status_normalized=WorkoutStatusNormalized.completed_normal)
    db.add(other);db.commit()
    with pytest.raises(McpSafeError):read_training_detail(db,users[0].id,f'workout_log:{other.id}',f'external_activity:{activity.id}')


@pytest.mark.parametrize('days',[7,28])
def test_same_window_matches_training_service_mcp_and_runner_state(sample,days):
    db,users,log,acts=sample
    from zoneinfo import ZoneInfo
    recent=get_recent_training_read(db,user_id=users[0].id,days=days,limit=20,as_of_date=DAY)
    paged=read_training(db,users[0].id,days=days)
    snapshot=RunnerStateService(db).get_current(users[0],generated_at=datetime(2026,7,21,12,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert recent.total_distance_km==paged.summary.total_distance_km==getattr(snapshot.recent_training,f'distance_{days}d_km')==18.5
    assert recent.total_sessions==paged.summary.total_sessions==getattr(snapshot.recent_training,f'completed_sessions_{days}d')==1
    assert recent.items[0].origin_source=='GARMIN'


def test_recovery_range_missing_reasons_and_user_isolation(sample):
    db,users,log,acts=sample
    result=read_recovery(db,users[0].id,start_date=DAY-timedelta(days=2),end_date=DAY)
    assert result.range_end==DAY and len(result.missing_dates)==2 and result.baseline is None
    row=result.daily_records[0]
    assert row.hrv_value==54 and row.muscle_soreness==2 and row.average_stress==24
    assert row.sleep_score is None and row.missing_reasons['sleep_score']=='SYNC_FAILED'
    assert row.missing_reasons['subjective_fatigue']=='NOT_RECORDED_OR_NOT_SYNCED'
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()
    assert read_recovery(db,users[1].id).data_status=='EMPTY'


def test_failed_sync_keeps_last_valid_metrics_and_hides_raw_error(sample):
    db,users,log,acts=sample
    connection=db.get(ExternalAccountConnection,acts[0].connection_id)
    connection.recovery_last_attempt_at=datetime(2026,7,21,9)
    connection.recovery_last_successful_sync_at=datetime(2026,7,20,9)
    connection.recovery_last_error_code='PRIVATE_SENTINEL'
    db.commit()
    result=read_recovery(db,users[0].id)
    assert result.sync_status=='FAILED'
    assert result.daily_records[0].hrv_value==54
    assert result.last_successful_sync_at=='2026-07-20T09:00:00'
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()


def test_mcp_protocol_schema_and_read_only_execution(sample,engine):
    db,users,log,acts=sample
    identity=McpRequestIdentity(users[0].id,frozenset({'mcp:read','mcp:recovery:read'}))
    server=create_mcp_server(McpExecutionContext(identity_provider=lambda:identity,session_factory=lambda:Session(engine)))
    def only_reads(_conn,_cursor,statement,*_args):
        assert statement.lstrip().split()[0].upper() not in {'INSERT','UPDATE','DELETE','ALTER','CREATE','DROP'}
    async def run():
        async with Client(server) as client:
            listed=(await client.list_tools()).tools
            assert len(listed)==6
            detail=await client.call_tool('get_training_detail',{'record_ref':f'workout_log:{log.id}','activity_ref':f'external_activity:{acts[1].id}'})
            assert detail.structured_content['data']['selected_activity']['distance_km']==15
            recovery=await client.call_tool('get_recovery_trend',{'start_date':str(DAY-timedelta(days=2)),'end_date':str(DAY)})
            assert recovery.structured_content['data']['daily_records'][0]['hrv_value']==54
    event.listen(engine,'before_cursor_execute',only_reads)
    try:asyncio.run(run())
    finally:event.remove(engine,'before_cursor_execute',only_reads)
