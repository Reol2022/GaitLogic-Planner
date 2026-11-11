"""Synthetic protocol/projection regressions. Never use runner health fixtures."""
import asyncio
import json
from datetime import date
from unittest.mock import Mock

from mcp import Client
from server.mcp.catalog import PRODUCT_VERSION, MCP_SERVER_VERSION, TOOL_ARGUMENTS
from server.mcp.knowledge import McpKnowledgeResourceService
from server.mcp.server import create_mcp_server
from server.mcp.adapters import McpToolAdapter
from server.mcp.context import McpExecutionContext, McpRequestIdentity
from server.mcp import facts_v2 as facts
from tests.test_mcp_facts_v2 import log
from fastapi.testclient import TestClient
from server.mcp.http import McpHttpDependencies, create_mcp_http_app
from planner_core.config import get_settings


def test_resource_capabilities_match_actual_tools_and_schema():
    async def run():
        async with Client(create_mcp_server()) as client:
            tools=(await client.list_tools()).tools
            resource=await client.read_resource('gaitlogic://capabilities')
            return tools,json.loads(resource.contents[0].text)['data']
    tools,data=asyncio.run(run())
    assert set(data['exposed_tools'])=={tool.name for tool in tools}==set(TOOL_ARGUMENTS)
    assert data['product_version']==PRODUCT_VERSION=='0.16.8'
    assert data['mcp_server_version']==MCP_SERVER_VERSION
    assert data['tool_scopes']['get_recovery_trend']=='mcp:recovery:read'
    assert data['pagination']['first_cursor']=='first'
    assert set(next(t for t in tools if t.name=='get_recent_training').input_schema['properties'])==TOOL_ARGUMENTS['get_recent_training']


def test_capability_document_never_reads_corpus_or_database():
    factory=Mock(side_effect=AssertionError('must not read any user data'))
    data=McpKnowledgeResourceService(corpus_factory=factory).capabilities()['data']
    assert len(data['exposed_tools'])==6
    factory.assert_not_called()


def test_http_version_is_visible_without_bypassing_authentication():
    factory=Mock()
    settings=get_settings().model_copy(update={'mcp_allowed_hosts':'testserver','mcp_allowed_origins':''})
    with TestClient(create_mcp_http_app(dependencies=McpHttpDependencies(settings=settings,session_factory=factory))) as client:
        response=client.post('/mcp',json={})
    assert response.status_code==401
    assert response.headers['X-GaitLogic-MCP-Version']==MCP_SERVER_VERSION
    factory.assert_not_called()


def test_legacy_page_one_gets_real_cursor_and_full_window_summary(monkeypatch):
    rows=[(log(i),None) for i in range(1,6)]
    monkeypatch.setattr(facts,'_query_logs',lambda *args:rows)
    monkeypatch.setattr(facts,'local_today',lambda:date(2026,7,22))
    db=Mock();db.scalars.return_value.all.return_value=[]
    adapter=McpToolAdapter(McpExecutionContext(identity_provider=lambda:McpRequestIdentity(101),session_factory=lambda:db))
    monkeypatch.setattr(adapter,'_invoke',lambda **kwargs:({'summary':{'total_sessions':5},'items':[{},{}]},None))
    first=adapter.get_recent_training(days=7,limit=2)
    assert first.status=='SUCCEEDED' and first.data.next_cursor
    assert len(first.data.items)==2 and first.data.summary.total_sessions==5 and first.data.summary.total_distance_km==25
    second=adapter.get_recent_training(days=7,limit=2,cursor=first.data.next_cursor)
    third=adapter.get_recent_training(days=7,limit=2,cursor=second.data.next_cursor)
    assert second.status==third.status=='SUCCEEDED'
    assert len(second.data.items)==2 and len(third.data.items)==1 and third.data.next_cursor is None
    assert first.data.summary==second.data.summary==third.data.summary
    assert len({item.record_ref for page in [first,second,third] for item in page.data.items})==5
    assert first.data.summary.session_count_basis=='COMPLETED_WORKOUT_LOGS'


def state_payload():
    return {'data_status':'PARTIAL','as_of_date':'2026-07-22','overall_state':'NORMAL','risk_level':'LOW',
            'data_quality':{'level':'PARTIAL','completeness':.5,'missing_fields':['rpe']},
            'metrics':{'sessions_7d':9,'sessions_28d':41,'completed_sessions_7d':7,'completed_sessions_28d':35,
                       'sleep_duration_minutes':999,'recovery_available_fields':'hrv_value', 'recovery_freshness':'STALE'},
            'warnings':[],'limitations':[],'evidence':[]}


def test_different_session_counts_remain_explicit_and_comparable():
    data=McpToolAdapter._runner_state(state_payload())
    assert data.metrics['sessions_7d']==9 and data.metrics['completed_sessions_7d']==7
    assert data.metrics['completed_sessions_28d']==35
    assert 'not completed' in data.metric_definitions['sessions_7d']
    assert 'total_sessions' in data.metric_definitions['completed_sessions_7d']
    assert data.assessment_scope=='TRAINING_RULES_ONLY'
    assert data.mcp_server_version==MCP_SERVER_VERSION


def test_low_load_risk_never_becomes_recovery_clearance_or_leaks_health():
    value=state_payload();data=McpToolAdapter._runner_state(value)
    assert data.training_load_risk_level=='LOW' and data.recovery_evidence_status=='UNKNOWN'
    assert 'sleep_duration_minutes' not in data.metrics
    assert 'not medical clearance' in data.risk_interpretation
    value['metrics']['recovery_freshness']='CURRENT'
    assert McpToolAdapter._runner_state(value).recovery_evidence_status=='PARTIAL'


def test_unknown_type_is_not_guessed_from_speed_or_planned_classification():
    record=log();record.workout_type=None;record.avg_pace_seconds_per_km=200;record.avg_heart_rate=160
    from types import SimpleNamespace
    item=facts.training_item(record,SimpleNamespace(main_type_normalized='recovery'))
    assert item.training_type=='unknown' and item.actual_training_type is None
    assert item.planned_training_type=='recovery'
