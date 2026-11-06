"""Pure synthetic contracts. No provider key, training records or network needed."""
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from planner_core.enums import WorkoutStatusNormalized
from server.common.exceptions import BadRequestError
from server.schemas.ai_plan import AIPlanGenerateRequest, WEEKDAYS
from server.services.ai_plan_context_service import aggregate_plan_rows, assess_feasibility
from server.services.ai_plan_constraints import validate_plan_constraints
from server.services.ai_plan_prompt import build_ai_plan_user_prompt


def request(**changes):
    return AIPlanGenerateRequest.model_validate({**dict(current_weekly_mileage_km=30, recent_4w_avg_mileage_km=30,
        available_training_days_per_week=4, target_distance='half_marathon', target_result='01:50:00',
        plan_start_date='2026-11-09',plan_weeks=1),**changes})


def output():
    return {'title':'Synthetic plan','start_date':'2026-11-09','end_date':'2026-11-15','target_race_date':None,
            'target_distance':'half_marathon','target_result':'01:50:00','summary':'Synthetic only','risk_notes':['训练草稿，需要人工确认'],
            'weeks':[{'block_name':'Week 1','planned_distance_km':20,'workouts':[
                {'date':'2026-11-10','main_type':'E','planned_content':'轻松跑8km','focus_note':'目的、注意与降级','target_pace_text':'','planned_distance_km':8,'planned_duration_minutes':48},
                {'date':'2026-11-14','main_type':'LSD','planned_content':'长距离12km','focus_note':'目的、注意与降级','target_pace_text':'','planned_distance_km':12,'planned_duration_minutes':60},
            ]}]}


def rows(count=56, missing=False):
    end=date(2026,11,6)
    return [(SimpleNamespace(id=i+1,activity_date=end-timedelta(days=i),status_normalized=WorkoutStatusNormalized.completed_normal,
             actual_distance_km=None if missing and i==0 else 5,actual_duration_seconds=1800,source_type='garmin',workout_type='easy',
             activity_fingerprint=f'synthetic-{i}',external_activity_id=None,updated_at=None),None) for i in range(count)]


def codes(issues):return {item.code for item in issues}


def test_full_window_not_twenty_item_list():
    basis=aggregate_plan_rows(rows(),date(2026,11,6))
    assert basis['record_count']==56 and basis['recent_28d_record_count']==28
    assert basis['recent_4w_avg_recorded_km']==35
    assert basis['training_days_per_week_28d']==7
    assert basis['complete_for_recorded_data'] and not basis['sync_coverage_verified']


@pytest.mark.parametrize('count,missing',[(0,False),(3,False),(56,True)])
def test_incomplete_records_are_not_zero_or_complete_baseline(count,missing):
    basis=aggregate_plan_rows(rows(count,missing),date(2026,11,6))
    assert basis['recent_4w_avg_recorded_km'] is None
    assert basis['weeks'][0]['recorded_distance_km'] is None if not count or missing else basis['weeks'][0]['recorded_distance_km']>0


def test_duplicate_candidates_and_pending_activities_are_explicit():
    values=rows();values.append(values[0]);basis=aggregate_plan_rows(values,date(2026,11,6),unresolved=2)
    assert basis['record_count']==56 and basis['duplicate_candidate_count']==1
    assert basis['unresolved_activity_count']==2 and not basis['complete_for_recorded_data']


def test_high_historical_mileage_and_challenging_target_warn_without_blocking():
    payload=request(recent_pb_distance='half_marathon',recent_pb_result='02:20:00')
    issues=assess_feasibility(payload,{'training':{'record_count':40,'complete_for_recorded_data':True,'recent_4w_avg_recorded_km':30,'previous_4w_avg_recorded_km':80}})
    assert {'VOLUME_CHANGED','CHALLENGING_TARGET'} <= codes(issues)
    assert all(item.severity!='error' for item in issues)


def test_impossible_rest_days_block_but_low_time_and_soft_long_day_warn():
    payload=request(fixed_rest_days=WEEKDAYS[:5],daily_available_minutes={day:10 for day in WEEKDAYS},long_run_preferred_day='周一')
    issues=assess_feasibility(payload,{})
    assert {'TRAINING_DAYS_CONFLICT','LIMITED_WEEKLY_TIME','LONG_RUN_REST_CONFLICT'} <= codes(issues)


@pytest.mark.parametrize('field,value',[('fixed_rest_days',['Funday']),('daily_available_minutes',{'周一':-5}),('long_run_preferred_day','周八'),('excluded_workout_types',['unsafe'])])
def test_constraint_schema_rejects_unknown_values(field,value):
    with pytest.raises(ValidationError):request(**{field:value})


def test_valid_plan_and_partial_recovery_do_not_require_rpe():
    validate_plan_constraints(output(),request(daily_available_minutes={'周二':50,'周六':60}))
    assert 'RECOVERY_LIMITED' in codes(assess_feasibility(request(),{}))


@pytest.mark.parametrize('change', ['rest','days','double','time','type','start','end','target','week_total','negative','nan','duration_missing','race','distance'])
def test_hard_constraint_violations_are_rejected(change):
    data=output();payload=request()
    if change=='rest':payload=request(fixed_rest_days=['周二'])
    elif change=='days':payload=request(available_training_days_per_week=1)
    elif change=='double':data['weeks'][0]['workouts'].append(deepcopy(data['weeks'][0]['workouts'][0]));data['weeks'][0]['planned_distance_km']=28
    elif change=='time':payload=request(daily_available_minutes={'周二':30})
    elif change=='type':payload=request(excluded_workout_types=['LSD'])
    elif change=='start':data['start_date']='2026-11-08'
    elif change=='end':data['end_date']='2026-11-16'
    elif change=='target':data['target_result']='01:20:00'
    elif change=='race':data['target_race_date']='2026-11-15'
    elif change=='distance':data['target_distance']='marathon'
    elif change=='week_total':data['weeks'][0]['planned_distance_km']=99
    elif change=='negative':data['weeks'][0]['workouts'][0]['planned_distance_km']=-1
    elif change=='nan':data['weeks'][0]['workouts'][0]['planned_distance_km']=float('nan')
    elif change=='duration_missing':payload=request(daily_available_minutes={'周二':60});data['weeks'][0]['workouts'][0].pop('planned_duration_minutes')
    with pytest.raises(BadRequestError):validate_plan_constraints(data,payload)


def test_cross_week_high_intensity_remains_blocked():
    data=output();data['end_date']='2026-11-22';data['weeks'][0]['workouts']=[{**data['weeks'][0]['workouts'][0],'date':'2026-11-15','main_type':'T1'}];data['weeks'][0]['planned_distance_km']=8
    data['weeks'].append({'planned_distance_km':8,'workouts':[{**data['weeks'][0]['workouts'][0],'date':'2026-11-16'}]})
    payload=request().model_copy(update={'plan_weeks':2})
    with pytest.raises(BadRequestError):validate_plan_constraints(data,payload)


def test_context_prompt_preserves_source_and_constraint_boundaries():
    prompt=build_ai_plan_user_prompt(request(),plan_context={'user_reported':{'recent_pb_result':'00:25:00'},'hard_constraints':{'can_double_run':False}})
    assert '不是Garmin验证成绩' in prompt and 'hard_constraints' in prompt
    assert '不虚构' in prompt and '未知周不是零跑量' in prompt
