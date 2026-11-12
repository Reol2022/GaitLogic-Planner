"""Independent client discovery, old call shapes and safe failure contracts."""
import asyncio
import json

from mcp.client import Client

from server.mcp.adapters import McpToolAdapter
from server.mcp.schemas import McpDataQuality
from server.mcp.facts_v2 import McpTrainingDetailResult
from server.mcp.errors import McpErrorCode
from tests.test_mcp_server import _server,_call,_context


def test_reconnection_rediscovers_six_tools_without_authorizing_or_querying_database():
    server,_,session=_server()
    async def discover():
        results=[]
        for _ in range(2):
            async with Client(server) as client:
                results.append((await client.list_tools()).tools)
        return results
    first,second=asyncio.run(discover())
    assert len(first)==len(second)==6
    assert [item.model_dump(mode='json') for item in first]==[item.model_dump(mode='json') for item in second]
    for tool in first:
        assert tool.description and tool.input_schema is not None and tool.output_schema is not None
        cache_sync = tool.name in {'get_recent_training', 'get_training_detail', 'get_runner_state', 'get_recovery_trend'}
        assert tool.annotations.read_only_hint is not cache_sync
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is cache_sync
        json.dumps(tool.model_dump(mode='json'))
    session.scalar.assert_not_called()
    session.execute.assert_not_called()


def test_legacy_input_shapes_work_and_recovery_still_needs_its_own_scope():
    server,_,_=_server()
    for name,args in [('get_today_plan',{}),('get_recent_training',{'days':7,'limit':20}),('get_runner_state',{})]:
        assert _call(server,name,args).structured_content['status']=='SUCCEEDED'
    # Recovery without its independent grant fails for permission, not a changed signature.
    recovery=_call(server,'get_recovery_trend',{'days':7}).structured_content
    assert recovery['error']['code']=='INSUFFICIENT_PERMISSION'


def test_stored_data_validation_failure_is_not_misreported_as_bad_client_input():
    context,session=_context()
    adapter=McpToolAdapter(context)
    def invalid_data(_db,_uid):return McpDataQuality(level='PARTIAL',completeness=9)
    result=adapter._read_fact(McpTrainingDetailResult,invalid_data)
    assert result.error.code==McpErrorCode.INTERNAL_SAFE_ERROR
    assert 'completeness' not in result.model_dump_json()
    session.rollback.assert_called_once();session.close.assert_called_once()


def test_database_failure_never_exposes_exception_text():
    context,session=_context()
    session.scalar.side_effect=RuntimeError('PRIVATE_SENTINEL')
    result=McpToolAdapter(context).get_training_detail(record_ref='workout_log:1')
    assert result.error.code==McpErrorCode.SERVICE_FAILURE
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()
    session.rollback.assert_called_once();session.close.assert_called_once()
