"""Synthetic factual conventions and public contract checks."""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from server.services.training_fact_policy import record_source, origin_source, recorded_distance
from server.services.runner_state_service import _effective_date, _window_metrics
from server.mcp.facts_v2 import read_recovery, read_training_detail
from server.mcp.errors import McpSafeError, McpErrorCode
from tests.test_runner_state_service import _row
from planner_core.enums import WorkoutMainTypeNormalized


@pytest.mark.parametrize('value,expected', [(None,'UNKNOWN'),('','UNKNOWN'),('other','UNKNOWN'),
    ('manual','MANUAL'),('garmin_sync','GARMIN'),('excel_import','IMPORT')])
def test_record_source_does_not_turn_unknown_into_manual(value,expected):
    assert record_source(value)==expected


def test_origin_is_separate_from_log_creation_source():
    log=SimpleNamespace(source_type='manual',field_sources_json={'actual_distance_km':'garmin','avg_heart_rate':'manual','notes':'PRIVATE'})
    assert origin_source(log)=='MIXED'
    log.field_sources_json={'actual_distance_km':'garmin'}
    assert origin_source(log)=='GARMIN'
    log.field_sources_json={}
    assert origin_source(log)=='UNKNOWN'


@pytest.mark.parametrize('value,expected',[(None,None),(-1,None),(float('nan'),None),(float('inf'),None),(0,0),(12.5,12.5)])
def test_distance_convention(value,expected):
    assert recorded_distance(value)==expected


@pytest.mark.parametrize('distance',[6,0,None])
def test_actual_date_and_positive_rest_label_are_counted_without_reclassification(distance):
    end=date(2026,7,21)
    (log,plan),_= _row(1,end,workout_type=WorkoutMainTypeNormalized.rest,distance=distance)
    plan.workout_date=end-timedelta(days=8)
    assert _effective_date(log,plan)==end
    metric=_window_metrics([(log,plan)],[plan],end-timedelta(days=6),end)
    assert metric.distance_km==distance and metric.completed_sessions==1
    assert metric.quality_sessions==0 and metric.planned_sessions==0
    log.activity_date=None
    assert _effective_date(log,plan)==plan.workout_date


@pytest.mark.parametrize('start,end',[(date(2026,7,1),None),(None,date(2026,7,1)),
    (date(2026,7,2),date(2026,7,1)),(date(2026,6,1),date(2026,7,1)),
    (date(2099,1,1),date(2099,1,2))])
def test_recovery_invalid_windows_are_rejected_before_query(start,end):
    db=Mock()
    with pytest.raises(McpSafeError) as exc:
        read_recovery(db,101,start_date=start,end_date=end)
    assert exc.value.code==McpErrorCode.INVALID_ARGUMENT
    db.scalars.assert_not_called()


@pytest.mark.parametrize('record,selected',[('garmin:1',None),('external_activity:0',None),
    ('workout_log:1','external_activity:0'),('external_activity:1','external_activity:2')])
def test_bad_refs_do_not_open_database(record,selected):
    db=Mock()
    with pytest.raises(McpSafeError):read_training_detail(db,101,record,selected)
    db.scalar.assert_not_called()
