"""Explicit loopback MySQL 8, freshly created gaitlogic_test_* schema and synthetic data only."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta,datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func,text,event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from planner_core.database.base import Base
from planner_core.database.models import UserAccount,WorkoutLog,TrainingCycle,AIPlanDraft,AIPlanJob,AIPlanQuota,PlannedWorkout,TrainingBlock
from planner_core.enums import WorkoutStatusNormalized,TrainingCycleStatus,AIPlanDraftStatus,AIPlanJobStatus
from server.services import ai_plan_service as service
from server.services.ai_plan_context_service import build_plan_context
from server.services.weekly_review_stats_service import local_today
from server.common.exceptions import BadRequestError,NotFoundError
from test_ai_plan_personalization import request,output


@pytest.fixture(scope='module')
def engine():
    raw=os.getenv('GAITLOGIC_AI_PLAN_TEST_DATABASE_URL')
    if not raw:pytest.skip('Explicit isolated local MySQL URL required')
    url=make_url(raw)
    assert url.host in {'127.0.0.1','localhost'} and url.port==3307 and (url.database or '').startswith('gaitlogic_test_ai_plan') and url.get_backend_name()=='mysql','Refusing non-isolated DB'
    name='gaitlogic_test_ai_plan_'+uuid4().hex[:12]
    admin=create_engine(url.set(database='mysql'))
    with admin.begin() as conn:conn.execute(text(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4'))
    test_engine=create_engine(url.set(database=name),pool_pre_ping=True)
    try:
        Base.metadata.create_all(test_engine)
        yield test_engine
    finally:
        test_engine.dispose()
        with admin.begin() as conn:conn.execute(text(f'DROP DATABASE `{name}`'))
        admin.dispose()


@pytest.fixture
def db(engine):
    with Session(engine,expire_on_commit=False) as session:
        yield session
        session.rollback()


@pytest.fixture
def users(db):
    accounts=[UserAccount(username='synthetic-plan-'+uuid4().hex[:10],password_hash='not-a-login',role='user',status='active') for _ in range(2)]
    db.add_all(accounts);db.commit();return accounts


@pytest.fixture
def provider(monkeypatch):
    runtime=SimpleNamespace(ai_model='synthetic-model',ai_base_url='https://example.invalid',ai_plan_daily_limit=8,ai_plan_cooldown_seconds=0,temperature=.2,top_p=.9)
    monkeypatch.setattr(service,'get_effective_ai_settings',lambda db:runtime)
    calls=[]
    def call(*args):calls.append({'called':True});return service.DeepSeekResult(content=json.dumps(output()),input_tokens=100,output_tokens=200,total_tokens=300)
    monkeypatch.setattr(service,'call_deepseek',call)
    return calls


def seed_training(db,user_id,count=56,missing=False):
    end=local_today()
    for index in range(count):db.add(WorkoutLog(user_id=user_id,activity_date=end-timedelta(days=index),status_normalized=WorkoutStatusNormalized.completed_normal,
        actual_distance_km=None if missing and index==0 else 5,actual_duration_seconds=1800,workout_type='easy',source_type='garmin',is_unplanned=True,
        activity_fingerprint=uuid4().hex))
    db.commit()


@pytest.mark.parametrize('count,missing',[(56,False),(4,False),(56,True),(0,False)])
def test_mysql_context_full_partial_and_empty_are_readonly_isolated(db,users,count,missing):
    seed_training(db,users[0].id,count,missing);seed_training(db,users[1].id,2)
    first=build_plan_context(db,users[0].id,request());second=build_plan_context(db,users[1].id,request())
    assert first.runner_facts['training']['record_count']==count
    assert second.runner_facts['training']['record_count']==2
    if count==56 and not missing:assert first.suggestions['recent_4w_avg_mileage_km']==35
    else:assert 'recent_4w_avg_mileage_km' not in first.suggestions
    assert build_plan_context(db,users[0].id,request()).fingerprint==first.fingerprint
    assert not db.new and not db.dirty


def test_mysql_generation_context_cache_quota_and_manual_provenance(db,users,provider):
    seed_training(db,users[0].id)
    payload=request(recent_4w_avg_mileage_km=48)
    draft=service.generate_ai_plan(db,users[0].id,payload)
    assert len(provider)==1
    job=db.get(AIPlanJob,draft.job_id)
    assert job.input_json['plan_context']['user_reported']['recent_4w_avg_mileage_km']==48
    assert job.input_json['plan_context']['runner_facts']['training']['recent_4w_avg_recorded_km']==35
    assert 'api_key' not in json.dumps(job.input_json)
    again=service.generate_ai_plan(db,users[0].id,payload)
    assert again.id==draft.id and len(provider)==1
    assert db.scalar(select(AIPlanQuota).where(AIPlanQuota.user_id==users[0].id)).used_count==1
    # MySQL DATETIME may round to the next second. Zero cooldown means disabled.
    quota=db.scalar(select(AIPlanQuota).where(AIPlanQuota.user_id==users[0].id));quota.last_generated_at=datetime.utcnow()+timedelta(seconds=1);db.commit()
    # A fact update invalidates the cache; no real provider involved.
    log=db.scalar(select(WorkoutLog).where(WorkoutLog.user_id==users[0].id));log.actual_distance_km=6;db.commit()
    assert service.generate_ai_plan(db,users[0].id,payload).id!=draft.id and len(provider)==2


def test_mysql_conflicting_request_never_calls_provider(db,users,provider):
    with pytest.raises(BadRequestError):service.generate_ai_plan(db,users[0].id,request(available_training_days_per_week=7,fixed_rest_days=['周一']))
    assert provider==[]


def test_mysql_model_violating_constraints_keeps_no_draft_and_no_quota_charge(db,users,provider,monkeypatch):
    monkeypatch.setattr(service,'call_deepseek',lambda *args:service.DeepSeekResult(content=json.dumps(output())))
    with pytest.raises(BadRequestError):service.generate_ai_plan(db,users[0].id,request(fixed_rest_days=['周二']))
    assert db.scalar(select(func.count()).select_from(AIPlanDraft).where(AIPlanDraft.user_id==users[0].id))==0
    assert db.scalar(select(AIPlanQuota).where(AIPlanQuota.user_id==users[0].id)).used_count==0
    assert db.scalar(select(AIPlanJob).where(AIPlanJob.user_id==users[0].id)).status==AIPlanJobStatus.failed


@pytest.mark.parametrize('activate',[False,True])
def test_mysql_apply_status_and_user_isolation(db,users,provider,activate):
    draft=service.generate_ai_plan(db,users[0].id,request())
    with pytest.raises(NotFoundError):service.apply_draft_to_training_plan(db,draft.id,users[1].id,activate=activate,confirm_high=True)
    cycle=service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=activate,confirm_high=True)
    with Session(db.bind) as check:
        saved=check.get(TrainingCycle,cycle.id)
        assert saved.status==(TrainingCycleStatus.active if activate else TrainingCycleStatus.draft)
        assert (saved.active_user_id==users[0].id)==activate
        assert check.get(AIPlanDraft,draft.id).status==AIPlanDraftStatus.accepted
        assert check.scalar(select(func.count()).select_from(PlannedWorkout).where(PlannedWorkout.cycle_id==cycle.id))==2
    with pytest.raises(BadRequestError):service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=activate,confirm_high=True)


def test_mysql_active_cycle_conflict_rolls_back_and_can_save_without_activation(db,users,provider):
    existing=TrainingCycle(user_id=users[0].id,name='Existing synthetic cycle',start_date=request().plan_start_date,end_date=request().plan_start_date+timedelta(days=10),status=TrainingCycleStatus.active,active_user_id=users[0].id)
    db.add(existing);db.commit();draft=service.generate_ai_plan(db,users[0].id,request())
    with pytest.raises(BadRequestError):service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=True,confirm_high=True)
    with Session(db.bind) as check:
        assert check.get(AIPlanDraft,draft.id).status==AIPlanDraftStatus.draft
        assert check.scalar(select(func.count()).select_from(TrainingCycle).where(TrainingCycle.user_id==users[0].id))==1
    cycle=service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=False,confirm_high=True)
    assert cycle.status==TrainingCycleStatus.draft


def test_mysql_apply_mid_flush_failure_is_atomic(db,users,provider):
    draft=service.generate_ai_plan(db,users[0].id,request())
    def fail(session,flush_context,instances):
        if any(isinstance(item,PlannedWorkout) for item in session.new):raise RuntimeError('synthetic apply failure')
    event.listen(db,'before_flush',fail)
    try:
        with pytest.raises(RuntimeError):service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=True,confirm_high=True)
    finally:event.remove(db,'before_flush',fail)
    with Session(db.bind) as check:
        assert check.get(AIPlanDraft,draft.id).status==AIPlanDraftStatus.draft
        assert check.scalar(select(func.count()).select_from(TrainingCycle).where(TrainingCycle.user_id==users[0].id))==0
        assert check.scalar(select(func.count()).select_from(TrainingBlock).where(TrainingBlock.user_id==users[0].id))==0
    assert service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=True,confirm_high=True).status==TrainingCycleStatus.active


def test_mysql_private_context_api_and_no_client_user_override(db,users):
    from server.main import app
    from server.api.deps import get_db,get_current_user
    seed_training(db,users[0].id,4);seed_training(db,users[1].id,12)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:users[0]
    try:
        client=TestClient(app)
        result=client.get('/api/ai-plan/context',params={'user_id':users[1].id})
        assert result.status_code==200 and result.json()['runner_facts']['training']['record_count']==4
        assessed=client.post('/api/ai-plan/context/assess',json=request().model_dump(mode='json'))
        assert assessed.status_code==200 and assessed.json()['schema_version']=='2.0'
    finally:app.dependency_overrides.clear()


def test_mysql_generation_save_failure_rolls_back_quota_and_draft(db,users,provider):
    def fail(session,flush_context,instances):
        if any(isinstance(item,AIPlanDraft) for item in session.new):raise RuntimeError('synthetic draft save failure')
    event.listen(db,'before_flush',fail)
    try:
        with pytest.raises(BadRequestError):service.generate_ai_plan(db,users[0].id,request())
    finally:event.remove(db,'before_flush',fail)
    with Session(db.bind) as check:
        assert check.scalar(select(func.count()).select_from(AIPlanDraft).where(AIPlanDraft.user_id==users[0].id))==0
        assert check.scalar(select(AIPlanQuota).where(AIPlanQuota.user_id==users[0].id)).used_count==0
        assert check.scalar(select(AIPlanJob).where(AIPlanJob.user_id==users[0].id)).status==AIPlanJobStatus.failed


def test_mysql_two_simultaneous_applications_create_one_cycle(db,users,provider,monkeypatch):
    draft=service.generate_ai_plan(db,users[0].id,request());draft_id=draft.id;user_id=users[0].id
    # Isolate the tested DB locking from the independently covered rule evaluation audit commit.
    from server.services import training_rule_loop_service
    monkeypatch.setattr(training_rule_loop_service,'validate_ai_plan_draft',lambda *args:SimpleNamespace(evaluation=SimpleNamespace(final_action='pass')))
    def apply():
        with Session(db.bind) as session:
            try:service.apply_draft_to_training_plan(session,draft_id,user_id,activate=True);return 'applied'
            except BadRequestError:return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:apply(),range(2)))==['applied','rejected']
    with Session(db.bind) as check:assert check.scalar(select(func.count()).select_from(TrainingCycle).where(TrainingCycle.user_id==user_id))==1


def test_mysql_completed_date_overlap_and_tampered_draft_are_blocked(db,users,provider):
    db.add(TrainingCycle(user_id=users[0].id,name='Completed synthetic',start_date=request().plan_start_date,end_date=request().plan_start_date+timedelta(days=2),status=TrainingCycleStatus.completed));db.commit()
    draft=service.generate_ai_plan(db,users[0].id,request())
    with pytest.raises(BadRequestError):service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=True,confirm_high=True)
    draft=service.get_draft(db,draft.id,users[0].id);draft.workouts[0].planned_distance_km=99;db.commit()
    with pytest.raises(BadRequestError):service.apply_draft_to_training_plan(db,draft.id,users[0].id,activate=False,confirm_high=True)


def test_mysql_api_snapshot_and_explicit_apply_modes(db,users,provider):
    from server.main import app
    from server.api.deps import get_db,get_current_user
    draft=service.generate_ai_plan(db,users[0].id,request())
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:users[0]
    try:
        client=TestClient(app)
        detail=client.get(f'/api/ai-plan/drafts/{draft.id}')
        assert detail.status_code==200
        assert detail.json()['plan_context']['hard_constraints']['can_double_run'] is False
        result=client.post(f'/api/ai-plan/drafts/{draft.id}/apply?confirm_high=true',json={'activate':False})
        assert result.status_code==200
        assert result.json()['cycle_status']=='draft' and result.json()['activated'] is False
        app.dependency_overrides[get_current_user]=lambda:users[1]
        assert client.get(f'/api/ai-plan/drafts/{draft.id}').status_code==404
    finally:app.dependency_overrides.clear()
