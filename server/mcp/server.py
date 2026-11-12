"""The local, stdio-only GaitLogic MCP server for v0.15-A."""

from __future__ import annotations

from typing import Annotated, Literal
from datetime import date
from mcp.types import ToolAnnotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from server.knowledge_retrieval.enums import KnowledgeCategory
from server.agent.tools.knowledge_tools import RetrieveTrainingKnowledgeInput
from server.mcp.adapters import DependenciesFactory, KnowledgeToolFactory, McpToolAdapter
from server.mcp.context import McpExecutionContext
from server.mcp.catalog import MCP_SERVER_VERSION, TOOL_ARGUMENTS
from server.mcp.knowledge import McpKnowledgeResourceService, register_knowledge_primitives
from server.mcp.schemas import (
    McpKnowledgeRetrievalResult,
    McpRecentTrainingResult,
    McpRunnerStateResult,
    McpTodayPlanResult,
)
from server.mcp.facts_v2 import McpRecoveryTrendResult, McpTrainingDetailResult


class GaitLogicMcpServer(MCPServer):
    """MCPServer with explicit closed-world argument validation.

    MCP SDK v2 derives function argument models with Pydantic's permissive
    default for unknown keys.  The public MCP boundary must be stricter: client
    arguments are a closed schema and may never smuggle identity fields through
    a tool call.
    """

    _ARGUMENT_NAMES = TOOL_ARGUMENTS

    async def call_tool(self, name, arguments, context=None):
        allowed = self._ARGUMENT_NAMES.get(name)
        if allowed is not None:
            if set(arguments) - allowed:
                raise ToolError("INVALID_ARGUMENT")
            if name == "get_recent_training":
                for key, lower, upper in (("days", 1, 90), ("limit", 1, 20)):
                    value = arguments.get(key)
                    if value is not None and (
                        isinstance(value, bool)
                        or not isinstance(value, int)
                        or not lower <= value <= upper
                    ):
                        raise ToolError("INVALID_ARGUMENT")
            if name == 'get_recovery_trend':
                value = arguments.get('days', 7)
                if type(value) is not int or not 1 <= value <= 28:
                    raise ToolError('INVALID_ARGUMENT')
            if name == "retrieve_training_knowledge":
                try:
                    RetrieveTrainingKnowledgeInput.model_validate(
                        {
                            "query": arguments.get("query"),
                            "top_k": arguments.get("top_k", 4),
                            "categories": arguments.get("categories", []),
                            "tags": arguments.get("tags", []),
                            "language": arguments.get("language", "zh-CN"),
                        }
                    )
                except Exception:
                    raise ToolError("INVALID_ARGUMENT") from None
        return await super().call_tool(name, arguments, context)


def create_mcp_server(
    execution_context: McpExecutionContext | None = None,
    *,
    dependencies_factory: DependenciesFactory | None = None,
    knowledge_tool_factory: KnowledgeToolFactory | None = None,
    knowledge_resource_service: McpKnowledgeResourceService | None = None,
) -> MCPServer:
    """Create a server with six read-only tools plus safe knowledge primitives.

    A production remote host must supply authenticated context in v0.15-B.  The
    command-line default purposely runs without identity, allowing protocol
    discovery while safely refusing all user-scoped reads.
    """

    context = execution_context or McpExecutionContext.unauthenticated_stdio()
    adapter = (
        McpToolAdapter(
            context,
            dependencies_factory=dependencies_factory,
            knowledge_tool_factory=knowledge_tool_factory,
        )
        if dependencies_factory is not None
        else McpToolAdapter(context, knowledge_tool_factory=knowledge_tool_factory)
    )
    mcp = GaitLogicMcpServer(
        name="gaitlogic-readonly",
        title="GaitLogic Planner",
        description="Read-only training facts from GaitLogic Planner.",
        version=MCP_SERVER_VERSION,
    )

    @mcp.tool(
        name="get_today_plan",
        description="Read today's plan for the trusted execution identity without changing it.",
        structured_output=True,
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )
    def get_today_plan() -> McpTodayPlanResult:
        return adapter.get_today_plan()

    @mcp.tool(
        name="get_recent_training",
        description="Read existing training facts; may enqueue background Garmin cache sync when the user enabled automatic sync. Does not change plans or manual input. Returns freshness status without waiting for Garmin. For stable pagination use cursor='first' then next_cursor with identical ranges. Summaries cover the full window.",
        structured_output=True,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def get_recent_training(
        days: Annotated[int, Field(ge=1, le=90)] = 7,
        limit: Annotated[int, Field(ge=1, le=20)] = 20,
        cursor: Annotated[str | None, Field(max_length=2048)] = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> McpRecentTrainingResult:
        return adapter.get_recent_training(days=days, limit=limit, cursor=cursor, start_date=start_date, end_date=end_date)

    @mcp.tool(
        name="get_runner_state",
        description="Read current deterministic Runner State. May enqueue background Garmin activity cache sync if enabled; returns existing facts without waiting. Does not change plans or manual input.",
        structured_output=True,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True),
    )
    def get_runner_state() -> McpRunnerStateResult:
        return adapter.get_runner_state()

    @mcp.tool(
        name="retrieve_training_knowledge",
        description="Retrieve canonical training-knowledge references without reading runner data or changing a plan.",
        structured_output=True,
        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
    )
    def retrieve_training_knowledge(
        query: Annotated[str, Field(min_length=1, max_length=4000)],
        top_k: Annotated[int, Field(ge=1, le=6)] = 4,
        categories: list[KnowledgeCategory] | None = None,
        tags: list[str] | None = None,
        language: Literal["zh-CN", "en-US"] = "zh-CN",
    ) -> McpKnowledgeRetrievalResult:
        return adapter.retrieve_training_knowledge(
            query=query,
            top_k=top_k,
            categories=[item.value for item in categories or []],
            tags=tags,
            language=language,
        )

    @mcp.tool(name='get_training_detail', description='Read a workout_log or external_activity reference. May enqueue background Garmin activity cache sync if enabled; no plan or manual-input changes. Select activity_ref for multi-activity logs. Legacy segments may be rollups; use normalized_segments with segment_validation. Activity RPE is not session RPE. No GPS or raw payload.', structured_output=True,
              annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    def get_training_detail(record_ref: Annotated[str, Field(pattern=r'^(workout_log|external_activity):[1-9][0-9]{0,17}$')],
        activity_ref: Annotated[str | None, Field(pattern=r'^external_activity:[1-9][0-9]{0,17}$')] = None) -> McpTrainingDetailResult:
        return adapter.get_training_detail(record_ref=record_ref, activity_ref=activity_ref)

    @mcp.tool(name='get_recovery_trend', description='Read up to 28 calendar days of stored recovery facts. Requires mcp:recovery:read consent. May enqueue background recovery cache sync only if user also enabled automatic recovery sync. Returns existing facts plus freshness; does not wait or change manual input. No health text notes.', structured_output=True,
              annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    def get_recovery_trend(days: Annotated[int, Field(ge=1, le=28)] = 7, start_date: date | None = None, end_date: date | None = None) -> McpRecoveryTrendResult:
        return adapter.get_recovery_trend(days=days,start_date=start_date,end_date=end_date)

    register_knowledge_primitives(mcp, knowledge_resource_service or McpKnowledgeResourceService())

    return mcp


mcp = create_mcp_server()


def main() -> None:
    """Run only the stdio transport; stdout remains reserved for MCP messages."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
