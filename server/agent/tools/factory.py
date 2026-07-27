from __future__ import annotations

from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentLimits
from server.agent.tool import AgentTool
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.planning_tools import (
    GetCurrentTrainingCycleTool,
    GetTodayWorkoutTool,
)
from server.agent.tools.rule_tools import EvaluateTodayWorkoutTool, GetTrainingRulesTool
from server.agent.tools.runner_state_tools import (
    GetRunnerStateHistoryTool,
    GetRunnerStateTool,
)
from server.agent.tools.training_tools import (
    GetRecentTrainingTool,
    GetTrainingDataQualityTool,
)

COACH_AGENT_TOOL_NAMES = frozenset(
    {
        "get_runner_state",
        "get_runner_state_history",
        "get_recent_training",
        "get_today_workout",
        "get_current_training_cycle",
        "get_training_rules",
        "evaluate_today_workout",
        "get_training_data_quality",
    }
)
COACH_AGENT_KNOWLEDGE_TOOL_NAME = "retrieve_training_knowledge"


def build_coach_agent_tool_registry(
    dependencies: CoachAgentToolDependencies,
    *,
    limits: AgentLimits | None = None,
    knowledge_tool: AgentTool | None = None,
) -> AgentToolRegistry:
    """Build one request-scoped registry with bounded read-only tools."""
    bounded = limits or AgentLimits()
    registry = AgentToolRegistry()
    for tool in (
        GetRunnerStateTool(dependencies, evidence_limit=bounded.max_evidence_items),
        GetRunnerStateHistoryTool(dependencies, history_limit=bounded.max_history_items),
        GetRecentTrainingTool(dependencies, item_limit=bounded.max_recent_training_items),
        GetTodayWorkoutTool(dependencies),
        GetCurrentTrainingCycleTool(dependencies),
        GetTrainingRulesTool(dependencies, rule_limit=bounded.max_rule_items),
        EvaluateTodayWorkoutTool(dependencies, item_limit=bounded.max_evidence_items),
        GetTrainingDataQualityTool(dependencies),
    ):
        registry.register(tool)
    if knowledge_tool is not None:
        if knowledge_tool.name != COACH_AGENT_KNOWLEDGE_TOOL_NAME:
            raise RuntimeError("Unexpected Coach knowledge tool.")
        registry.register(knowledge_tool)
    actual = {definition.name for definition in registry.list_tools()}
    expected = (
        COACH_AGENT_TOOL_NAMES | {COACH_AGENT_KNOWLEDGE_TOOL_NAME}
        if knowledge_tool is not None
        else COACH_AGENT_TOOL_NAMES
    )
    if actual != expected:
        raise RuntimeError("Coach Agent production tool registry is incomplete or unsafe.")
    return registry
