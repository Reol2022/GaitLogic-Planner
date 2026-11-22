"""Independent SDK tools/list check; no user identity, database or Provider calls."""
import asyncio
import hashlib
import json
from mcp import Client
from server.mcp.server import create_mcp_server
from server.mcp.catalog import MCP_SERVER_VERSION, TOOL_ARGUMENTS


def validate_contract(tools):
    found = {tool.name: tool for tool in tools}
    assert set(found) == set(TOOL_ARGUMENTS), 'Tool registry mismatch'
    for name, tool in found.items():
        assert set(tool.input_schema.get('properties', {})) == set(TOOL_ARGUMENTS[name]), 'Input contract changed'
    schema = found['get_training_detail'].output_schema
    assert 'freshness' in schema['properties'], 'Freshness not discoverable'
    detail = schema['$defs']['McpTrainingDetail']['properties']
    for field in ('normalized_segments', 'segment_validation', 'activity_classification', 'raw_segments_complete', 'normalized_structure_complete', 'raw_segment_distance_consistent'):
        assert field in detail, 'Missing detail output field'
    assert 'structure_complete' in schema['$defs']['SegmentValidation']['properties']
    assert 'detail_status' in schema['$defs']['SegmentValidation']['properties']
    assert 'confirmation_status' in schema['$defs']['ActivityClassification']['properties']
    assert 'event_type_source' in schema['$defs']['ActivityClassification']['properties']
    assert 'data_freshness' in schema['$defs']['SyncFreshness']['properties']
    for field in ('last_job', 'last_job_by_scope', 'blocking_job'):
        assert field in schema['$defs']['SyncFreshness']['properties'], 'Missing scope job receipt'
    runner = found['get_runner_state'].output_schema
    assert 'sync_provenance' in runner['$defs']['McpRunnerState']['properties']
    recent = found['get_recent_training'].output_schema
    assert 'unresolved_activity_count' in recent['$defs']['McpRecentTrainingSummary']['properties']
    material = [{'name': name, 'input': found[name].input_schema, 'output': found[name].output_schema} for name in sorted(found)]
    return {'status': 'PASS', 'server_version': MCP_SERVER_VERSION, 'tools': len(found),
        'schema_sha256': hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()}


async def check():
    async with Client(create_mcp_server()) as client:
        return validate_contract((await client.list_tools()).tools)


if __name__ == '__main__':
    print(json.dumps(asyncio.run(check())))
