"""The local, stdio-only GaitLogic MCP server for v0.15-A."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from server.knowledge_retrieval.enums import KnowledgeCategory
from server.agent.tools.knowledge_tools import RetrieveTrainingKnowledgeInput
from server.mcp.adapters import DependenciesFactory, KnowledgeToolFactory, McpToolAdapter
from server.mcp.context import McpExecutionContext
from server.mcp.knowledge import McpKnowledgeResourceService, register_knowledge_primitives
from server.mcp.schemas import (
    McpKnowledgeRetrievalResult,
    McpRecentTrainingResult,
    McpRunnerStateResult,
    McpTodayPlanResult,
)


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
        "retrieve_training_knowledge": frozenset({"query", "top_k", "categories", "tags", "language"}),
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
    """Create a server with four read-only tools plus safe knowledge primitives.

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

    @mcp.tool(
        name="retrieve_training_knowledge",
        description="Retrieve canonical training-knowledge references without reading runner data or changing a plan.",
        structured_output=True,
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

    register_knowledge_primitives(mcp, knowledge_resource_service or McpKnowledgeResourceService())

    return mcp


mcp = create_mcp_server()


def main() -> None:
    """Run only the stdio transport; stdout remains reserved for MCP messages."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
