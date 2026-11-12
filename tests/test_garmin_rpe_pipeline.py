"""Synthetic self-evaluation and detail contracts; no real runner fixtures."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from server.integrations.activity_provider.self_evaluation import normalize_rpe, apply_log_rpe, log_rpe_metadata, effective_log_rpe
from server.integrations.activity_provider.garmin import GarminActivityProvider
from server.integrations.activity_provider.base import ProviderActivity, ProviderError
from server.services.garmin_sync_service import _copy_activity_metrics, _replace_laps, _enrich_activity_summary
from server.services.garmin_detail_refresh_service import refresh_details
from server.agent.coach_task_classifier import CoachTaskClassifier
from server.agent.enums import AgentIntent
from server.agent.training_date_range import parse_training_date_range


def evidence(value=80):
    return normalize_rpe({'summaryDTO':{'directWorkoutRpe':value}},fetched_at=datetime(2026,6,1,tzinfo=timezone.utc))


@pytest.mark.parametrize('raw,expected',[(10,1),(50,5),(80,8),(100,10),(None,None),(0,None),(-10,None),(110,None),(15,None),(True,None),('80',None),(float('nan'),None)])
def test_rpe_normalization_never_guesses_scales(raw,expected):
    result=evidence(raw)
    assert result['value']==expected
    assert result['raw_field']=='summaryDTO.directWorkoutRpe'
    assert bool(result['missing_reason']) == (expected is None)
    assert normalize_rpe({'rpe':8})['value'] is None


def test_detail_reads_nested_summary_rpe_and_laps_without_fit():
    client=SimpleNamespace(get_activity=lambda _: {'activityId':'synthetic',
        'summaryDTO':{'startTimeLocal':'2026-06-01 19:00:00','startTimeGMT':'2026-06-01 11:00:00',
            'distance':12000,'duration':3600,'directWorkoutRpe':80},'activityTypeDTO':{'typeKey':'running'}},
        get_activity_splits=lambda _: {'lapDTOs':[{'lapIndex':1,'distance':1000,'duration':240}]})
    provider=GarminActivityProvider();provider._client=client
    result=provider.fetch_activity_summary('synthetic')
    assert result.details_fetched and result.laps_fetched and result.rpe_evidence['value']==8
    assert result.distance_m==12000 and result.start_time_utc==datetime(2026,6,1,11)
    assert len(result.laps)==1


def test_manual_rpe_and_explicit_manual_clear_win():
    activities=[SimpleNamespace(field_sources_json={'rpe_evidence':evidence()})]
    for value in (6,None):
        log=SimpleNamespace(rpe=value,field_sources_json={'rpe':'manual'})
        apply_log_rpe(log,activities)
        assert log.rpe==value and log.field_sources_json['rpe']=='manual'


def test_late_rating_update_idempotence_missing_values_and_multiple_activities():
    log=SimpleNamespace(rpe=None,field_sources_json={})
    row=SimpleNamespace(field_sources_json={'rpe_evidence':evidence()})
    apply_log_rpe(log,[row]);apply_log_rpe(log,[row])
    assert log.rpe==8 and log_rpe_metadata(log)['source']=='GARMIN'
    row.field_sources_json={'rpe_evidence':evidence(50)}
    apply_log_rpe(log,[row]);assert log.rpe==5
    row.field_sources_json={'rpe_evidence':evidence(None)}
    apply_log_rpe(log,[row]);assert log.rpe==5
    missing=SimpleNamespace(rpe=None,field_sources_json={})
    apply_log_rpe(missing,[row,row]);assert missing.rpe is None
    assert missing.field_sources_json['garmin_rpe_evidence']['missing_reason']=='MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING'


def test_single_activity_rating_is_withdrawn_when_session_gains_another_activity():
    activity = SimpleNamespace(field_sources_json={'rpe_evidence': evidence(30)})
    log = SimpleNamespace(rpe=None, field_sources_json={})
    apply_log_rpe(log, [activity])
    assert log.rpe == 3
    apply_log_rpe(log, [activity, activity])
    assert log.rpe is None
    assert activity.field_sources_json['rpe_evidence']['value'] == 3
    assert log_rpe_metadata(log)['missing_reason'] == 'MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING'


def test_stale_persisted_rating_is_withheld_readonly_but_manual_session_rating_survives():
    stale = SimpleNamespace(rpe=3, field_sources_json={'rpe':'garmin',
        'garmin_rpe_evidence':{'missing_reason':'MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING'}})
    assert effective_log_rpe(stale) is None and stale.rpe == 3
    assert effective_log_rpe(stale, linked_activity_count=2) is None
    assert effective_log_rpe(stale, linked_activity_count=1) is None
    stale.field_sources_json['rpe'] = 'manual'
    assert effective_log_rpe(stale, linked_activity_count=2) == 3


def test_list_sync_does_not_erase_prior_rpe_or_laps():
    row=SimpleNamespace(field_sources_json={'rpe_evidence':evidence()})
    summary=ProviderActivity('synthetic',None,'running',None,datetime(2026,6,1),distance_m=12000)
    _copy_activity_metrics(row,summary)
    assert row.field_sources_json['rpe_evidence']['value']==8
    db=Mock();_replace_laps(db,row,summary);db.execute.assert_not_called()


def test_detail_failure_keeps_summary_and_no_raw_error():
    provider=Mock();provider.fetch_activity_summary.side_effect=ProviderError('TIMEOUT','PRIVATE ERROR')
    summary=ProviderActivity('synthetic',None,'running',None,datetime(2026,6,1),distance_m=12000)
    result=_enrich_activity_summary(provider,summary)
    assert result.distance_m==12000 and result.rpe_evidence['missing_reason']=='DETAIL_FETCH_FAILED'
    assert 'PRIVATE' not in str(result.rpe_evidence)


def test_refresh_rejects_oversize_or_future_before_query():
    db=Mock()
    with pytest.raises(Exception):refresh_details(db,user_id=1,start=date(2026,1,1),end=date(2026,6,1))
    with pytest.raises(Exception):refresh_details(db,user_id=1,start=date(2099,1,1),end=date(2099,1,1))
    db.scalars.assert_not_called()


@pytest.mark.parametrize('message',['分析我今天训练','复盘昨天的跑步','分析workout_log:123的分段'])
def test_actual_analysis_does_not_route_to_plan_recommendation(message):
    assert CoachTaskClassifier.classify(message)==AgentIntent.PERSONAL_TRAINING_ANALYSIS


def test_daily_scope_uses_local_day_and_keeps_explicit_rolling_window():
    now=datetime(2026,6,2,12,tzinfo=timezone.utc)
    assert parse_training_date_range('分析今天训练',now).start_date==date(2026,6,2)
    assert parse_training_date_range('昨天训练',now).start_date==date(2026,6,1)
    assert parse_training_date_range('今天分析最近28天',now).days==28
    assert CoachTaskClassifier.classify('今天该怎么跑')==AgentIntent.TODAY_RECOMMENDATION


def test_current_cycle_returns_only_persisted_target_and_marks_inactive_reference():
    from tests.agent_tool_fakes import FakeDependencies, NOW
    from server.agent.tools.planning_tools import GetCurrentTrainingCycleTool
    from server.agent.tools.schemas import EmptyToolInput
    from server.agent.schemas import AgentRequest, AgentContext
    deps=FakeDependencies()
    deps.cycle=SimpleNamespace(id=7,name='Synthetic active cycle',status='active',actual_start_date=None,
        actual_end_date=None,start_date=NOW.date(),end_date=NOW.date(),goal='Synthetic goal',blocks=[],
        target_race_name='Synthetic race',target_race_date=NOW.date(),target_result='01:30:00')
    request=AgentRequest(user_id=91,intent=AgentIntent.PERSONAL_TRAINING_ANALYSIS,message='Synthetic')
    context=AgentContext(request_id=request.request_id,user_id=91,intent=request.intent,current_time=NOW,timezone='Asia/Shanghai')
    result=GetCurrentTrainingCycleTool(deps).execute(EmptyToolInput(),context)
    assert result.is_active and result.target_result=='01:30:00' and result.target_race_name=='Synthetic race'
    deps.cycle=None
    result=GetCurrentTrainingCycleTool(deps).execute(EmptyToolInput(),context)
    assert not result.is_active and result.target_result is None


def test_refresh_dry_run_never_restores_a_provider_or_commits(monkeypatch):
    from server.services import garmin_sync_service
    provider=Mock()
    monkeypatch.setattr(garmin_sync_service,'_provider_for_connection',provider)
    db=Mock();db.scalars.return_value=[]
    result=refresh_details(db,user_id=91,start=date(2026,1,1),end=date(2026,1,20))
    assert result['dry_run'] and result['updated']==0
    provider.assert_not_called();db.commit.assert_not_called()
