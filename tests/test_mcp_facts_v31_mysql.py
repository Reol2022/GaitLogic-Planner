"""v3.1 boundary, privacy and bounded-query acceptance on synthetic MySQL data."""
from datetime import datetime,timedelta
from time import perf_counter
from statistics import median
from zoneinfo import ZoneInfo
from uuid import uuid4

import pytest
from sqlalchemy import event,select

from tests.test_mcp_facts_v3_mysql import engine,sample,DAY
from planner_core.database.models import ExternalActivity,PlannedWorkout,WorkoutLog,DailyRecoveryCheckin,ExternalAccountConnection
from planner_core.enums import WorkoutMainTypeNormalized,WorkoutStatusNormalized
from server.mcp.facts_v2 import read_training,read_training_detail,read_recovery
from server.services.training_load_service import get_recent_training_read
from server.services.runner_state_service import RunnerStateService


@pytest.mark.parametrize('days',[7,28])
def test_actual_date_boundaries_fallback_and_missing_values_match_across_services(sample,days):
    db,users,original,acts=sample
    start=DAY-timedelta(days=days-1)
    template=db.get(PlannedWorkout,original.planned_workout_id)
    fallback=PlannedWorkout(user_id=users[0].id,cycle_id=template.cycle_id,block_id=template.block_id,
        workout_date=start,session_index=2,planned_content='Synthetic fallback',main_type_normalized=WorkoutMainTypeNormalized.easy,sort_order=2)
    db.add(fallback);db.flush()
    for day,distance,plan in [(start,3,None),(start-timedelta(days=1),9,None),(None,4,fallback),(DAY,None,None)]:
        db.add(WorkoutLog(user_id=users[0].id,activity_date=day,actual_distance_km=distance,planned_workout_id=plan.id if plan else None,
            workout_type='easy',status_normalized=WorkoutStatusNormalized.completed_normal,source_type='legacy_unknown',is_unplanned=plan is None))
    db.commit()
    recent=get_recent_training_read(db,user_id=users[0].id,days=days,limit=20,as_of_date=DAY)
    mcp=read_training(db,users[0].id,days=days)
    state=RunnerStateService(db).get_current(users[0],generated_at=datetime(2026,7,21,12,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert recent.total_distance_km==mcp.summary.total_distance_km==getattr(state.recent_training,f'distance_{days}d_km')==25.5
    assert recent.total_sessions==mcp.summary.total_sessions==getattr(state.recent_training,f'completed_sessions_{days}d')==4
    assert recent.start_date==mcp.range_start==getattr(state.identity,f'calculation_window_start_{days}d')==start
    assert all(start<=item.date<=DAY for item in mcp.items)
    assert len([item for item in mcp.items if item.distance_km is None])==1
    assert any(item.source=='UNKNOWN' for item in mcp.items)
    if days==28:assert start.month!=DAY.month


def test_current_sync_failure_cannot_relabel_historical_missing_fields(sample):
    db,users,log,acts=sample
    row=db.scalar(select(DailyRecoveryCheckin).where(DailyRecoveryCheckin.user_id==users[0].id))
    row.checkin_date=DAY-timedelta(days=1)
    row.device_data_status='PARTIAL'
    connection=db.get(ExternalAccountConnection,acts[0].connection_id)
    connection.recovery_last_attempt_at=datetime(2026,7,21,9)
    connection.recovery_last_successful_sync_at=datetime(2026,7,20,9)
    connection.recovery_last_error_code='PRIVATE_SENTINEL'
    db.commit()
    result=read_recovery(db,users[0].id,start_date=row.checkin_date,end_date=row.checkin_date)
    assert result.sync_status=='FAILED'  # current connection status only
    assert result.daily_records[0].device_data_status=='PARTIAL'
    assert result.daily_records[0].missing_reasons['sleep_score']=='NOT_RECORDED_OR_NOT_SYNCED'
    assert result.daily_records[0].hrv_value==54


def test_one_activity_auto_selection_and_no_laps_do_not_fabricate_data(sample):
    db,users,log,acts=sample
    solo=WorkoutLog(user_id=users[0].id,activity_date=DAY,source_type='manual',is_unplanned=True,
        status_normalized=WorkoutStatusNormalized.completed_normal,actual_distance_km=1)
    db.add(solo);db.flush()
    activity=ExternalActivity(user_id=users[0].id,connection_id=acts[0].connection_id,workout_log_id=solo.id,
        provider='garmin',external_activity_id='synth-'+uuid4().hex,connector_version='synthetic',activity_type='running',
        start_time_local=datetime(2026,7,21,12),activity_date=DAY,distance_m=1000,duration_seconds=300)
    db.add(activity);db.commit()
    result=read_training_detail(db,users[0].id,f'workout_log:{solo.id}')
    assert not result.selection_required and result.linked_activity_count==1
    assert result.selected_activity.activity_ref==f'external_activity:{activity.id}'
    assert result.selected_activity.distance_km==1 and result.selected_activity.duration_seconds==300
    assert result.selected_activity.max_heart_rate_bpm is None
    assert result.selected_activity.average_stride_length_m is None
    assert not result.segments_available and not result.segments_complete and not result.segments
    assert result.selected_activity.verification_status=='PROVIDER_RECORDED_NOT_INDEPENDENTLY_VERIFIED'


def test_selected_detail_has_constant_query_count_with_twenty_associated_activities(sample,engine):
    db,users,log,acts=sample
    counts=[];durations=[]
    def measure():
        queries=[]
        def collect(_conn,_cursor,statement,*_args):
            if statement.lstrip().upper().startswith('SELECT'):queries.append(statement)
        event.listen(engine,'before_cursor_execute',collect)
        try:
            started=perf_counter()
            result=read_training_detail(db,users[0].id,f'workout_log:{log.id}',f'external_activity:{acts[1].id}')
            durations.append((perf_counter()-started)*1000)
            counts.append(len(queries))
            assert len(result.segments)==2
        finally:event.remove(engine,'before_cursor_execute',collect)
    for _ in range(5):measure()
    for n in range(17):
        db.add(ExternalActivity(user_id=users[0].id,connection_id=acts[0].connection_id,workout_log_id=log.id,
            provider='garmin',external_activity_id='synth-'+uuid4().hex,connector_version='synthetic',activity_type='running',
            start_time_local=datetime(2026,7,21,12),activity_date=DAY))
    db.commit()
    for _ in range(5):measure()
    assert counts==[6]*10
    ordered=sorted(durations)
    print(f'synthetic detail n=10 associated_activities=3/20 SELECTs=6 p50_ms={median(durations):.2f} p95_ms={ordered[-1]:.2f}')


def test_existing_page_http_apis_match_selected_facts_without_writes(sample,engine,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from planner_core.config import get_settings
    from server.api.deps import get_db,get_current_user
    from server.api.routes import runner_state,workout_logs,garmin_sync
    from server.services.training_fact_policy import record_source
    db,users,log,acts=sample
    monkeypatch.setenv('GARMIN_SYNC_ROLLOUT_MODE','all');get_settings.cache_clear()
    class FixedTimeState(RunnerStateService):
        def get_current(self,user,**kwargs):
            return super().get_current(user,generated_at=datetime(2026,7,21,12,tzinfo=ZoneInfo('Asia/Shanghai')))
    monkeypatch.setattr(runner_state,'RunnerStateService',FixedTimeState)
    app=FastAPI()
    for router in [runner_state.router,workout_logs.router,garmin_sync.router]:app.include_router(router,prefix='/api')
    def sessions():
        with Session(engine) as session:yield session
    app.dependency_overrides[get_db]=sessions
    app.dependency_overrides[get_current_user]=lambda:users[0]
    def reject_writes(_conn,_cursor,statement,*_args):
        assert statement.lstrip().split()[0].upper() not in {'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP'}
    event.listen(engine,'before_cursor_execute',reject_writes)
    try:
        with TestClient(app) as client:
            response=client.get(f'/api/workout-logs/{log.planned_workout_id}')
            assert response.status_code==200
            page_log=response.json()
            detail=read_training_detail(db,users[0].id,f'workout_log:{log.id}',f'external_activity:{acts[1].id}')
            assert detail.record.record_ref==f"workout_log:{page_log['id']}"
            assert detail.record.date.isoformat()==page_log['activity_date']
            assert detail.record.distance_km==float(page_log['actual_distance_km'])
            assert detail.record.duration_seconds==page_log['actual_duration_seconds']
            assert detail.record.source==record_source(page_log['source_type'])
            assert detail.record.average_heart_rate==page_log['avg_heart_rate']
            response=client.get('/api/integrations/garmin/activities')
            assert response.status_code==200
            page_activity=next(item for item in response.json() if item['id']==acts[1].id)
            selected=detail.selected_activity
            assert selected.activity_ref==f"external_activity:{page_activity['id']}"
            assert selected.date.isoformat()==page_activity['activity_date']
            assert selected.distance_km==float(page_activity['distance_m'])/1000
            assert selected.duration_seconds==page_activity['duration_seconds']
            assert selected.average_heart_rate_bpm==page_activity['average_heart_rate_bpm']
            response=client.get('/api/runner-state/current')
            assert response.status_code==200
            assert response.json()['snapshot']['recent_training']['distance_7d_km']==read_training(db,users[0].id).summary.total_distance_km
    finally:
        event.remove(engine,'before_cursor_execute',reject_writes)
        get_settings.cache_clear()
