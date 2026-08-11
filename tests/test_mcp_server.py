from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from unittest.mock import Mock

from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from sqlalchemy import event, func, select

from planner_core.database.models import PlannedWorkout, RunnerStateSnapshotRecord, WorkoutLog
from server.agent.schemas import AgentContext
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.mcp.adapters import McpToolAdapter
from server.mcp.context import McpExecutionContext, McpRequestIdentity
from server.mcp.errors import McpErrorCode
from server.mcp.server import create_mcp_server
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer
from tests.agent_tool_fakes import FakeDependencies, NOW
from tests.test_agent_training_integration import agent_context, make_database


EXPECTED_TOOLS = {
    "get_today_plan",
    "get_recent_training",
    "get_runner_state",
    "retrieve_training_knowledge",
}


def _context(
    *,
    identity: McpRequestIdentity | None = McpRequestIdentity(101),
    tracer: SafeTracer | None = None,
    session: Mock | None = None,
) -> tuple[McpExecutionContext, Mock]:
    active_session = session or Mock()
    return (
        McpExecutionContext(
            identity_provider=lambda: identity,
            session_factory=lambda: active_session,
            tracer=tracer or SafeTracer(enabled=False),
        ),
        active_session,
    )


def _server(
    *,
    identity: McpRequestIdentity | None = McpRequestIdentity(101),
    tracer: SafeTracer | None = None,
    dependencies: FakeDependencies | None = None,
) -> tuple[object, FakeDependencies, Mock]:
    context, session = _context(identity=identity, tracer=tracer)
    fake = dependencies or FakeDependencies()
    return create_mcp_server(context, dependencies_factory=lambda _db: fake), fake, session


def _call(server, name: str, arguments: dict | None = None):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})

    return asyncio.run(run())


def _list(server):
    async def run():
        async with Client(server) as client:
            return await client.list_tools()

    return asyncio.run(run())


def test_mcp_server_lists_only_four_strict_read_only_tools() -> None:
    server, _fake, _session = _server()
    tools = _list(server).tools
    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    schemas = {tool.name: tool.input_schema for tool in tools}
    assert schemas["get_today_plan"].get("properties", {}) == {}
    assert schemas["get_runner_state"].get("properties", {}) == {}
    assert set(schemas["get_recent_training"]["properties"]) == {"days", "limit"}
    assert set(schemas["retrieve_training_knowledge"]["properties"]) == {
        "query", "top_k", "categories", "tags", "language"
    }
    assert all("user_id" not in str(schema) and "email" not in str(schema) for schema in schemas.values())


def test_mcp_tools_return_structured_fictional_results_and_trusted_identity_only() -> None:
    server, fake, session = _server()
    today = _call(server, "get_today_plan")
    recent = _call(server, "get_recent_training", {"days": 7, "limit": 5})
    state = _call(server, "get_runner_state")
    assert today.structured_content["status"] == "SUCCEEDED"
    assert recent.structured_content["data"]["summary"]["total_sessions"] == 0
    assert state.structured_content["data"]["as_of_date"] == NOW.date().isoformat()
    assert fake.seen_user_ids and set(fake.seen_user_ids) == {101}
    assert "user_id" not in str(recent.structured_content)
    assert "brief_review" not in str(recent.structured_content)
    assert session.rollback.call_count == 3
    assert session.close.call_count == 3


def test_mcp_rejects_extra_identity_and_invalid_arguments_with_safe_code() -> None:
    server, _fake, _session = _server()
    for arguments in (
        {"user_id": 999},
        {"email": "fictional@example.test"},
        {"days": 29},
        {"days": True},
    ):
        result = _call(server, "get_recent_training", arguments)
        assert result.is_error is True
        assert result.structured_content is None
        assert "INVALID_ARGUMENT" in str(result.content)
        assert "traceback" not in str(result.content).lower()


def test_mcp_missing_identity_is_a_structured_safe_error() -> None:
    server, _fake, session = _server(identity=None)
    result = _call(server, "get_runner_state")
    assert result.structured_content == {
        "status": "FAILED",
        "error": {
            "code": McpErrorCode.AUTH_CONTEXT_MISSING.value,
            "message": "An authenticated execution context is required.",
        },
        "data": None,
    }
    session.rollback.assert_not_called()
    session.close.assert_not_called()


def test_adapter_uses_existing_coach_registry_and_default_service_dependencies() -> None:
    context, _session = _context()
    adapter = McpToolAdapter(context)
    assert adapter._dependencies_factory.__self__ is CoachAgentToolDependencies
    assert adapter._dependencies_factory.__func__ is CoachAgentToolDependencies.from_session.__func__
    assert "build_coach_agent_tool_registry" in Path("server/mcp/adapters.py").read_text(encoding="utf-8")


def test_mcp_actual_service_calls_are_read_only_and_user_scoped() -> None:
    engine, factory = make_database()
    writes: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def collect_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    with factory() as db:
        before = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in (PlannedWorkout, WorkoutLog, RunnerStateSnapshotRecord)
        }
    context = McpExecutionContext(
        identity_provider=lambda: McpRequestIdentity(901), session_factory=factory
    )
    adapter = McpToolAdapter(context)
    assert adapter.get_today_plan().status == "SUCCEEDED"
    assert adapter.get_recent_training(days=7, limit=20).status == "SUCCEEDED"
    assert adapter.get_runner_state().status == "SUCCEEDED"
    with factory() as db:
        after = {
            model.__tablename__: db.scalar(select(func.count()).select_from(model))
            for model in (PlannedWorkout, WorkoutLog, RunnerStateSnapshotRecord)
        }
    assert before == after
    assert writes == []


def test_mcp_service_failure_never_leaks_orm_or_traceback() -> None:
    class BrokenDependencies(FakeDependencies):
        def current_runner_state(self, user_id: int):
            del user_id
            raise RuntimeError("mysql://private-host/secret")

    server, _fake, _session = _server(dependencies=BrokenDependencies())
    result = _call(server, "get_runner_state")
    serialized = str(result.structured_content)
    assert result.structured_content["error"]["code"] == McpErrorCode.SERVICE_FAILURE.value
    assert "mysql" not in serialized.lower()
    assert "traceback" not in serialized.lower()
    assert "_sa_instance_state" not in serialized


def test_mcp_trace_and_metrics_are_best_effort_and_safe() -> None:
    trace_sink = InMemoryTraceSink()
    metric_sink = InMemoryMetricsSink()
    tracer = SafeTracer(
        FanoutTraceSink(trace_sink, MetricsTraceSink(MetricsRecorder(metric_sink)))
    )
    server, _fake, _session = _server(tracer=tracer)
    result = _call(server, "get_recent_training", {"days": 7, "limit": 5})
    assert result.structured_content["status"] == "SUCCEEDED"
    assert [(span.component, span.operation) for span in trace_sink.spans] == [
        ("tool", "invoke"),
        ("mcp", "tool"),
        ("mcp", "request"),
    ]
    registry_span, tool_span, request_span = trace_sink.spans
    assert tool_span.parent_span_id == request_span.span_id
    assert registry_span.parent_span_id == tool_span.span_id
    assert tool_span.metadata == {
        "transport": "stdio",
        "tool_name": "get_recent_training",
        "operation_type": "mcp_tool",
        "status": "SUCCEEDED",
    }
    assert metric_sink.counter("mcp_tool_call_count") == 1
    assert metric_sink.counter("mcp_tool_success") == 1
    assert metric_sink.latency_count("mcp_tool_latency_ms") == 1


def test_mcp_disabled_and_broken_trace_or_metrics_sinks_do_not_change_tool_result() -> None:
    class BrokenTraceSink:
        def write(self, _span) -> None:
            raise RuntimeError("sink unavailable")

    class BrokenMetricsSink:
        def record(self, _point) -> None:
            raise RuntimeError("metrics unavailable")

    disabled_server, _fake, _session = _server(tracer=SafeTracer(enabled=False))
    broken_server, _fake, _session = _server(
        tracer=SafeTracer(
            FanoutTraceSink(
                BrokenTraceSink(),
                MetricsTraceSink(MetricsRecorder(BrokenMetricsSink())),
            )
        )
    )
    assert _call(disabled_server, "get_today_plan").structured_content["status"] == "SUCCEEDED"
    assert _call(broken_server, "get_today_plan").structured_content["status"] == "SUCCEEDED"


def test_mcp_stdio_server_starts_and_stdout_remains_protocol_clean() -> None:
    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "server.mcp.server"],
            cwd=".",
        )
        async with Client(stdio_client(parameters)) as client:
            tools = await client.list_tools()
            result = await client.call_tool("get_runner_state")
            return tools, result

    tools, result = asyncio.run(run())
    assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
    assert result.structured_content["error"]["code"] == McpErrorCode.AUTH_CONTEXT_MISSING.value


def test_mcp_module_does_not_change_existing_coach_agent_registry() -> None:
    registry = build_coach_agent_tool_registry(FakeDependencies())
    result = registry.invoke("get_recent_training", {"days": 7, "limit": 20}, agent_context(901, "WEEKLY_REVIEW"))
    assert result.status.value == "SUCCEEDED"
