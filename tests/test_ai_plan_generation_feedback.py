"""Synthetic model output only. No credentials, network or business database."""
import json
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from server.services import ai_plan_service as service
from server.services.ai_plan_calendar import plan_calendar
from server.services.ai_plan_context_service import assess_feasibility
from server.services.ai_plan_constraints import validate_plan_constraints
from server.services.ai_plan_prompt import build_ai_plan_user_prompt, build_ai_plan_system_prompt
from server.common.exceptions import BadRequestError
from test_ai_plan_personalization import request, output


@pytest.mark.parametrize('days,weeks,last_days', [(94,14,3),(98,14,7),(1,1,1),(6,1,6),(8,2,1),(29,5,1)])
def test_calendar_covers_race_with_partial_final_week(days,weeks,last_days):
    start=date(2026,11,9); race=start+timedelta(days=days-1)
    calendar=plan_calendar(start,weeks,race)
    assert not calendar.error and calendar.end==race
    assert len(calendar.week_ranges)==weeks
    last=calendar.week_ranges[-1]
    assert (date.fromisoformat(last['end_date'])-date.fromisoformat(last['start_date'])).days+1==last_days


def test_full_weeks_without_race_and_stage_before_distant_race():
    start=date(2026,11,9)
    assert plan_calendar(start,8).end==start+timedelta(days=55)
    assert plan_calendar(start,8,start+timedelta(days=140)).end==start+timedelta(days=55)


def test_excess_weeks_and_race_before_start_have_actionable_blockers():
    start=date(2026,11,9);race=start+timedelta(days=93)
    assert '最多可安排 14' in plan_calendar(start,15,race).error
    assert plan_calendar(start,1,start-timedelta(days=1)).error
    issues=assess_feasibility(request(plan_weeks=15,target_race_date=race),{})
    assert any(i.code=='PLAN_WEEKS_EXCEED_RACE' and i.severity=='error' for i in issues)


def test_partial_week_is_accepted_but_post_race_workout_stays_blocked():
    data=output();data['end_date']='2026-11-14';data['target_race_date']='2026-11-14'
    payload=request(target_race_date='2026-11-14')
    validate_plan_constraints(data,payload)
    data['weeks'][0]['workouts'][1]['date']='2026-11-15'
    with pytest.raises(BadRequestError):validate_plan_constraints(data,payload)


def test_prompt_has_exact_calendar_and_required_output_fields():
    payload=request(plan_weeks=14,target_race_date=date(2026,11,9)+timedelta(days=93))
    prompt=build_ai_plan_user_prompt(payload,plan_context={'hard_constraints':{}})
    assert '2027-02-10' in prompt and 'week_date_ranges' in prompt
    system=build_ai_plan_system_prompt()
    assert '"target_distance"' in system and '"planned_duration_minutes"' in system
    assert '最后一周' in system


def test_missing_request_metadata_is_filled_without_changing_workouts():
    data=output();original=deepcopy(data['weeks'])
    for field in ['target_distance','start_date','end_date','target_race_date','target_result']:data.pop(field)
    validated=service.validate_generated_plan(json.dumps(data),request())
    assert validated['target_distance']=='half_marathon' and validated['end_date']=='2026-11-15'
    assert validated['weeks']==original


def invoke(monkeypatch,values,payload=None):
    calls=[]
    def fake(*args):
        calls.append(args)
        return values[len(calls)-1]
    monkeypatch.setattr(service,'call_deepseek',fake)
    result=service.generate_validated_plan('system','synthetic prompt',payload or request(),SimpleNamespace())
    return calls,result


def response(data):
    return service.DeepSeekResult(content=json.dumps(data),input_tokens=100,output_tokens=200,total_tokens=300)


def test_schema_retry_once_and_usage_includes_both_calls(monkeypatch):
    malformed=output();malformed['weeks'][0]['workouts'][0].pop('focus_note')
    calls,(data,usage)=invoke(monkeypatch,[response(malformed),response(output())])
    assert len(calls)==2 and '结构校验' in calls[1][1]
    assert data['weeks']==output()['weeks'] and usage.total_tokens==600
    assert usage.input_tokens==200 and usage.output_tokens==400


def test_parse_retry_can_recover_without_persisting_bad_output(monkeypatch):
    calls,_=invoke(monkeypatch,[service.DeepSeekResult(content='{broken'),response(output())])
    assert len(calls)==2 and '{broken' not in calls[1][1]


def test_retry_is_bounded_and_reports_safe_failure(monkeypatch,caplog):
    count=[]
    def fake(*args):count.append(1);return service.DeepSeekResult(content='private-raw-invalid')
    monkeypatch.setattr(service,'call_deepseek',fake)
    with pytest.raises(service.AIPlanOutputError) as error:
        service.generate_validated_plan('s','u',request(),SimpleNamespace())
    assert len(count)==2 and error.value.category=='OUTPUT_PARSE_FAILED'
    assert 'private-raw-invalid' not in caplog.text+error.value.message
    assert '未扣除' in error.value.message


@pytest.mark.parametrize('violation',['rest','target','date','total','duration','high'])
def test_real_constraint_violations_do_not_trigger_format_retry(monkeypatch,violation):
    data=output();payload=request();calls=[]
    if violation=='rest':payload=request(fixed_rest_days=['周二'])
    elif violation=='target':data['target_result']='00:45:00'
    elif violation=='date':data['start_date']='2026-11-08'
    elif violation=='total':data['weeks'][0]['planned_distance_km']=999
    elif violation=='duration':payload=request(daily_available_minutes={'周二':30})
    else:
        data['weeks'][0]['workouts'][0]['main_type']='T1'
        data['weeks'][0]['workouts'][1].update(date='2026-11-11',main_type='I')
    def fake(*args):calls.append(1);return response(data)
    monkeypatch.setattr(service,'call_deepseek',fake)
    with pytest.raises(service.AIPlanOutputError) as error:
        service.generate_validated_plan('s','u',payload,SimpleNamespace())
    assert len(calls)==1 and error.value.category in {'CONSTRAINT_VIOLATION','SAFETY_BOUNDARY'}


@pytest.mark.parametrize('result,category',[(service.DeepSeekResult(content='{}',finish_reason='length'),'OUTPUT_TRUNCATED'),(service.DeepSeekResult(content=''),'OUTPUT_EMPTY')])
def test_truncation_and_empty_outputs_have_specific_errors(monkeypatch,result,category):
    calls=[]
    def fake(*args):calls.append(1);return result
    monkeypatch.setattr(service,'call_deepseek',fake)
    with pytest.raises(service.AIPlanOutputError) as error:service.generate_validated_plan('s','u',request(),SimpleNamespace())
    assert len(calls)==1 and error.value.category==category


def test_generation_orchestration_saves_partial_week_and_charges_only_success(monkeypatch):
    data=output();data.update(end_date='2026-11-14',target_race_date='2026-11-14')
    payload=request(target_race_date='2026-11-14')
    job=SimpleNamespace(id=1,user_id=123)
    quota=SimpleNamespace(used_count=0,last_generated_at=None)
    db=SimpleNamespace(rollback=lambda:None,get=lambda *args:job,commit=lambda:None)
    runtime=SimpleNamespace(ai_model='synthetic',ai_base_url='https://example.invalid',ai_plan_daily_limit=5,
                            ai_plan_cooldown_seconds=0,temperature=.2,top_p=.9)
    monkeypatch.setattr(service,'get_effective_ai_settings',lambda db:runtime)
    monkeypatch.setattr(service,'get_or_create_preference',lambda *args:None)
    monkeypatch.setattr(service,'preference_to_prompt_dict',lambda *args:{})
    monkeypatch.setattr(service,'build_plan_context',lambda *args:SimpleNamespace(feasibility=[],model_dump=lambda **kw:{}))
    monkeypatch.setattr(service,'return_cached_draft_if_same_prompt',lambda *args:None)
    monkeypatch.setattr(service,'check_ai_plan_quota',lambda *args:quota)
    monkeypatch.setattr(service,'save_job',lambda *args:job)
    monkeypatch.setattr(service,'call_deepseek',lambda *args:response(data))
    saved=[]
    monkeypatch.setattr(service,'save_draft',lambda db,job,value:saved.append(value) or value)
    result=service.generate_ai_plan(db,123,payload)
    assert result['end_date']=='2026-11-14' and len(saved)==1 and quota.used_count==1
    # A second invalid output cannot create a second applicable draft or charge.
    data['weeks'][0]['workouts'][1]['date']='2026-11-15'
    with pytest.raises(service.AIPlanOutputError):service.generate_ai_plan(db,123,payload)
    assert len(saved)==1 and quota.used_count==1
