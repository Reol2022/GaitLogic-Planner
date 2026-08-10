"""The local, stdio-only GaitLogic MCP server for v0.15-A."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from server.mcp.adapters import DependenciesFactory, McpToolAdapter
from server.mcp.context import McpExecutionContext
from server.mcp.schemas import McpRecentTrainingResult, McpRunnerStateResult, McpTodayPlanResult


class GaitLogicMcpServer(MCPServer):
    """MCPServer with explicit closed-world argument validation.

    MCP SDK v2 derives function argument models with Pydantic's permissive
    default for unknown keys.  The public MCP boundary must be stricter: client
    arguments are a closed schema and may never smuggle identity fields through
    a tool call.
    """

    _ARGUMENT_NAMES = {
        "get_today_plan": frozenset(),
        "get_recent_training": frozenset({"days", "limit"}),
        "get_runner_state": frozenset(),
    }

    async def call_tool(self, name, arguments, context=None):
        allowed = self._ARGUMENT_NAMES.get(name)
        if allowed is not None:
            if set(arguments) - allowed:
                raise ToolError("INVALID_ARGUMENT")
            if name == "get_recent_training":
                for key, lower, upper in (("days", 1, 28), ("limit", 1, 20)):
                    value = arguments.get(key)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or not lower <= value <= upper
                    ):
                        raise ToolError("INVALID_ARGUMENT")
        return await super().call_tool(name, arguments, context)


def create_mcp_server(
    execution_context: McpExecutionContext | None = None,
    *,
    dependencies_factory: DependenciesFactory | None = None,
) -> MCPServer:
    """Create a server with exactly the three v0.15-A read-only tools.

    A production remote host must supply authenticated context in v0.15-B.  The
    command-line default purposely runs without identity, allowing protocol
    discovery while safely refusing all user-scoped reads.
    """

    context = execution_context or McpExecutionContext.unauthenticated_stdio()
    adapter = (
        McpToolAdapter(context, dependencies_factory=dependencies_factory)
        if dependencies_factory is not None
        else McpToolAdapter(context)
    )
    mcp = GaitLogicMcpServer(
        name="gaitlogic-readonly",
        title="GaitLogic Planner",
        description="Read-only training facts from GaitLogic Planner.",
        version="0.15.0-A",
    )

    @mcp.tool(
        name="get_today_plan",
        description="Read today's plan for the trusted execution identity without changing it.",
        structured_output=True,
    )
    def get_today_plan() -> McpTodayPlanResult:
        return adapter.get_today_plan()

    @mcp.tool(
        name="get_recent_training",
        description="Read bounded recent training facts for the trusted execution identity.",
        structured_output=True,
    )
    def get_recent_training(
        days: Annotated[int, Field(ge=1, le=28)] = 7,
        limit: Annotated[int, Field(ge=1, le=20)] = 20,
    ) -> McpRecentTrainingResult:
        return adapter.get_recent_training(days=days, limit=limit)

    @mcp.tool(
        name="get_runner_state",
        description="Read the current deterministic Runner State for the trusted execution identity.",
        structured_output=True,
    )
    def get_runner_state() -> McpRunnerStateResult:
        return adapter.get_runner_state()

    return mcp


mcp = create_mcp_server()


def main() -> None:
    """Run only the stdio transport; stdout remains reserved for MCP messages."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
