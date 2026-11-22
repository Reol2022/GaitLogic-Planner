"""Pure synthetic quality and SDK contract checks."""
import asyncio
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace as Row
from unittest.mock import Mock
import pytest

from tests.test_training_segment_facts import lap
from server.services.lap_storage_policy import replacement_decision
from server.services.training_fact_policy import classification_evidence, classification_coverage
from server.integrations.activity_provider.garmin import GarminActivityProvider


def test_actual_classification_coverage_does_not_promote_unknown_or_legacy_sources():
    logs = [Row(workout_type='interval_speed', source_type='manual', field_sources_json={'workout_type':'manual'}, actual_distance_km=8),
        Row(workout_type='tempo', source_type='garmin_sync', field_sources_json={}, actual_distance_km=8),
        Row(workout_type='easy', source_type='manual', field_sources_json={}, actual_distance_km=8)]
    assert classification_evidence(logs[0]) == {'source':'USER_REPORTED_FACT','confirmation_status':'USER_CONFIRMED'}
    assert classification_evidence(logs[1])['source'] == 'UNKNOWN'
    assert classification_evidence(logs[2])['source'] == 'RECORDED_UNVERIFIED'
    coverage = classification_coverage(logs)
    assert coverage['classified_sessions'] == 2 and coverage['unclassified_sessions'] == 1
    assert coverage['classification_coverage'] == 0.6667 and coverage['key_session_count_status'] == 'PARTIAL'
    assert classification_coverage([])['classification_coverage'] is None


def test_explicit_manual_type_edit_on_a_synced_record_keeps_user_reported_provenance():
    log=Row(workout_type='interval_speed', source_type='garmin_sync', field_sources_json={'workout_type':'manual_edit'}, actual_distance_km=8)
    assert classification_evidence(log)=={'source':'USER_REPORTED_FACT','confirmation_status':'USER_CONFIRMED'}
    assert classification_coverage([log])['key_session_count_status']=='COMPLETE'


@pytest.mark.parametrize('kind', ['summary', 'fewer', 'conflict', 'incomplete'])
def test_structural_degradations_are_not_accepted(kind):
    summary = Row(distance_m=1200, duration_seconds=300, timer_time_seconds=300)
    old = [lap(1,start=0), lap(2,start=150)]
    if kind == 'summary':
        new = [lap(1,distance=1200,seconds=300,kind='RWD_RUN')]
    elif kind == 'fewer':
        new = [lap(1,distance=1200,seconds=300,start=0)]
    elif kind == 'conflict':
        new = [lap(1,start=0),lap(2,start=20)]
    else:
        new = [lap(1,start=0,distance=500),lap(2,start=150,distance=500)]
    assert replacement_decision(summary,old,summary,new)[0] is False


def test_fallback_uses_bounded_existing_typed_endpoint_without_guessing_repetitions(monkeypatch):
    import server.integrations.activity_provider.garmin as garmin
    provider = GarminActivityProvider()
    provider._client = Row(get_activity=Mock(), get_activity_splits=Mock(), get_activity_typed_splits=Mock())
    responses = iter([{'activityId':'synthetic','startTimeLocal':'2026-01-01 08:00:00','activityType':{'typeKey':'running'},
        'summaryDTO':{'distance':1200,'duration':300}},
        {'splitSummaries':[{'splitType':'INTERVAL_ACTIVE','distance':1200,'duration':300}]},
        {'lapDTOs':[{'lapIndex':1,'distance':600,'duration':150},{'lapIndex':2,'distance':600,'duration':150}]}])
    call = Mock(side_effect=lambda *_: next(responses))
    monkeypatch.setattr(garmin,'_bounded_detail_call',call)
    result = provider.fetch_activity_summary('synthetic')
    assert call.call_count == 3 and len(result.laps) == 2
    assert all(row.classification_source == 'garmin_lap_dto' for row in result.laps)
    assert 'garmin_splits' in result.raw_payload and 'garmin_typed_splits' in result.raw_payload


def test_public_output_schemas_match_independent_client_discovery():
    from scripts.check_mcp_contract import check
    result = asyncio.run(check())
    assert result['status'] == 'PASS' and result['tools'] == 6
    assert len(result['schema_sha256']) == 64


def test_capabilities_no_longer_claim_entire_server_is_side_effect_free():
    from server.mcp.knowledge import McpKnowledgeResourceService
    value = McpKnowledgeResourceService().capabilities()['data']
    assert value['read_only'] is False and value['business_plan_read_only'] is True
    assert value['external_cache_updates_possible'] is True
