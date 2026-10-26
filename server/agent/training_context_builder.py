from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from server.agent.context import AgentContextBuilder
from server.agent.enums import (
    AgentIntent,
    AgentToolStatus,
    AgentTraceEventType,
    AgentTraceStatus,
)
from server.agent.knowledge_references import KNOWLEDGE_TOOL_NAME
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext, AgentContextSeed, AgentNotice, AgentRequest
from server.agent.trace import AgentTrace

_PRELOADS: dict[AgentIntent, tuple[tuple[str, dict[str, int | str]], ...]] = {
    AgentIntent.CASUAL_CONVERSATION: (),
    AgentIntent.COACH_CAPABILITY_QUERY: (),
    AgentIntent.TODAY_RECOMMENDATION: (
        ("get_runner_state", {}),
        ("get_today_workout", {}),
        ("get_recent_training", {"days": 7, "limit": 20}),
        ("get_training_data_quality", {"window_days": 14}),
        ("evaluate_today_workout", {}),
    ),
    AgentIntent.WEEKLY_REVIEW: (
        ("get_runner_state", {}),
        ("get_runner_state_history", {"limit": 7}),
        ("get_recent_training", {"days": 7, "limit": 20}),
        ("get_current_training_cycle", {}),
        ("get_training_data_quality", {"window_days": 14}),
    ),
    AgentIntent.EXPLAIN_RUNNER_STATE: (
        ("get_runner_state", {}),
        ("get_runner_state_history", {"limit": 7}),
        ("get_training_data_quality", {"window_days": 14}),
    ),
    AgentIntent.GENERAL_TRAINING_QUESTION: (
        ("get_training_rules", {"scope": "GENERAL"}),
    ),
    AgentIntent.PERSONAL_TRAINING_ANALYSIS: (
        ("get_runner_state", {}),
        ("get_runner_state_history", {"limit": 7}),
        ("get_recent_training", {"days": 28, "limit": 20}),
        ("get_current_training_cycle", {}),
        ("get_today_workout", {}),
        ("get_training_data_quality", {"window_days": 28}),
    ),
    AgentIntent.PLAN_ADJUSTMENT_ANALYSIS: (
        ("get_runner_state", {}),
        ("get_runner_state_history", {"limit": 7}),
        ("get_recent_training", {"days": 28, "limit": 20}),
        ("get_current_training_cycle", {}),
        ("get_today_workout", {}),
        ("get_training_data_quality", {"window_days": 28}),
    ),
    AgentIntent.PERSONAL_TRAINING_FACT_QUERY: (),
    AgentIntent.PERSONAL_TRAINING_STATUS: (
        ("get_runner_state", {}),
        ("get_recent_training", {"days": 14, "limit": 14}),
        ("get_training_data_quality", {"window_days": 14}),
    ),
    AgentIntent.UNKNOWN: (),
}

_FIELD_BY_TOOL = {
    "get_runner_state": "runner_state",
    "get_runner_state_history": "runner_state_history",
    "get_recent_training": "recent_training",
    "get_today_workout": "today_workout",
    "get_current_training_cycle": "current_cycle",
    "evaluate_today_workout": "today_evaluation",
    "get_training_data_quality": "data_quality",
}

_KNOWLEDGE_PRELOAD_INTENTS = frozenset(
    {
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.EXPLAIN_RUNNER_STATE,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    }
)


def merge_agent_tool_results(context: AgentContext, new_results: list) -> AgentContext:
    """Merge validated Tool Results into canonical request-local context."""

    values = context.model_dump(mode="python")
    missing = dict(context.missing_reasons)
    for result in new_results:
        if result.status != AgentToolStatus.SUCCEEDED or not isinstance(result.data, dict):
            missing[result.tool_name] = (
                result.safe_error_code.value
                if result.safe_error_code is not None
                else "AGENT_TOOL_EXECUTION_FAILED"
            )
            continue
        if result.data.get("data_status") in {"NOT_FOUND", "UNKNOWN"}:
            missing[result.tool_name] = str(result.data.get("data_status"))
        else:
            missing.pop(result.tool_name, None)
        if result.tool_name == "get_training_rules":
            values["applicable_rules"] = list(result.data.get("rules", []))
        else:
            field = _FIELD_BY_TOOL.get(result.tool_name)
            if field:
                values[field] = result.data
    values["tool_results"] = [*context.tool_results, *new_results]
    values["missing_reasons"] = missing
    return AgentContext.model_validate(values)


class AgentTrainingContextBuilder(AgentContextBuilder):
    """Build intent-aware context exclusively through the registered tool boundary."""

    def __init__(self, *, registry: AgentToolRegistry, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.registry = registry

    def build(
        self,
        request: AgentRequest,
        seed: AgentContextSeed | None = None,
        *,
        trace: AgentTrace | None = None,
    ) -> AgentContext:
        context = super().build(request, seed)
        results = list(context.tool_results)
        values = context.model_dump(mode="python")
        missing = dict(context.missing_reasons)
        preloads = self._preloads_for_request(request, context.current_time)
        available_tools = {
            definition.name for definition in self.registry.list_tools(request.intent)
        }
        if (
            request.intent in _KNOWLEDGE_PRELOAD_INTENTS
            and KNOWLEDGE_TOOL_NAME in available_tools
        ):
            preloads.append((KNOWLEDGE_TOOL_NAME, {"query": request.message}))
        preload_limit = min(self.limits.max_tool_calls, len(preloads))
        for name, arguments in preloads[:preload_limit]:
            started = perf_counter()
            if trace is not None:
                trace.add_event(
                    AgentTraceEventType.CONTEXT_TOOL_STARTED,
                    AgentTraceStatus.STARTED,
                    tool_name=name,
                )
            result = self.registry.invoke(name, arguments, context)
            if trace is not None:
                trace.add_event(
                    AgentTraceEventType.CONTEXT_TOOL_COMPLETED,
                    AgentTraceStatus.SUCCEEDED
                    if result.status == AgentToolStatus.SUCCEEDED
                    else AgentTraceStatus.FAILED,
                    tool_name=name,
                    safe_error_code=result.safe_error_code,
                    duration_ms=(perf_counter() - started) * 1000,
                )
            context = merge_agent_tool_results(context, [result])
            results = list(context.tool_results)
            values = context.model_dump(mode="python")
            missing = dict(context.missing_reasons)
        return self._bounded_context(context)

    @staticmethod
    def _preloads_for_request(request: AgentRequest, current_time) -> list[tuple[str, dict[str, int | str]]]:
        if request.intent != AgentIntent.PERSONAL_TRAINING_FACT_QUERY:
            return list(_PRELOADS[request.intent])
        normalized = request.message.lower()
        target_date = current_time.date() + timedelta(days=1) if any(
            marker in normalized for marker in ("明天", "明日", "tomorrow")
        ) else current_time.date()
        return [("get_today_workout", {"target_date": target_date.isoformat()})]

    def _bounded_context(self, context: AgentContext) -> AgentContext:
        values = deepcopy(context.model_dump(mode="python"))
        trimmed = False
        values["applicable_rules"] = values["applicable_rules"][: self.limits.max_rule_items]
        if values.get("runner_state_history"):
            history = values["runner_state_history"]
            history["items"] = history.get("items", [])[: self.limits.max_history_items]
        if values.get("recent_training"):
            recent = values["recent_training"]
            recent["items"] = recent.get("items", [])[: self.limits.max_recent_training_items]
        if values.get("runner_state"):
            state = values["runner_state"]
            state["evidence"] = state.get("evidence", [])[: self.limits.max_evidence_items]
        values = self._trim_strings(values, 500)

        def size() -> int:
            return len(json.dumps(values, ensure_ascii=False, sort_keys=True, default=str))

        if size() > self.limits.max_context_chars:
            trimmed = True
            values["applicable_rules"] = []
        if size() > self.limits.max_context_chars and values.get("runner_state_history"):
            trimmed = True
            values["runner_state_history"]["items"] = []
        if size() > self.limits.max_context_chars and values.get("recent_training"):
            trimmed = True
            values["recent_training"]["items"] = []
        if size() > self.limits.max_context_chars:
            trimmed = True
            for result in values["tool_results"]:
                result["data"] = None
        if trimmed:
            values["limitations"] = [
                *values.get("limitations", []),
                AgentNotice(
                    code="CONTEXT_TRIMMED",
                    message="Low-priority context details were deterministically trimmed to the configured size limit.",
                ).model_dump(),
            ]
        if size() > self.limits.max_context_chars:
            raise ValueError("agent context exceeds configured size after deterministic trimming")
        try:
            return AgentContext.model_validate(values)
        except ValidationError as exc:
            raise ValueError("trimmed agent context is invalid") from exc

    @classmethod
    def _trim_strings(cls, value: Any, limit: int) -> Any:
        if isinstance(value, str):
            return value[:limit]
        if isinstance(value, list):
            return [cls._trim_strings(item, limit) for item in value]
        if isinstance(value, dict):
            return {key: cls._trim_strings(item, limit) for key, item in value.items()}
        return value
