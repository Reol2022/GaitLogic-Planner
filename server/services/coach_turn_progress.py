"""Safe, user-facing progress snapshots for one Coach conversation turn.

The snapshot deliberately contains only bounded stage names and aggregate
summaries.  It must never become a second copy of prompts, tool payloads or
provider reasoning.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from server.agent.enums import AgentToolStatus


class CoachTurnStage(StrEnum):
    QUEUED = "QUEUED"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    FACTS_LOADING = "FACTS_LOADING"
    FACTS_READY = "FACTS_READY"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TERMINAL_STAGES = frozenset({CoachTurnStage.COMPLETED, CoachTurnStage.FAILED})


def stage_is_terminal(stage: CoachTurnStage | str) -> bool:
    return CoachTurnStage(stage) in TERMINAL_STAGES


def safe_facts_summary(tool_results: list[Any]) -> list[dict[str, str | int]]:
    """Create a small aggregate summary from already-authorized tool results.

    Counts only come from explicit result collections.  A failed tool is never
    presented as a successful read, and no raw training fields leave the agent
    context through this helper.
    """
    items: list[dict[str, str | int]] = []
    failures = 0
    for result in tool_results:
        name = getattr(result, "tool_name", "")
        status = getattr(result, "status", None)
        data = getattr(result, "data", None)
        if status != AgentToolStatus.SUCCEEDED:
            failures += 1
            continue
        if not isinstance(data, dict) or data.get("data_status") in {"NOT_FOUND", "UNKNOWN"}:
            continue
        if name == "get_recent_training":
            records = data.get("items")
            if isinstance(records, list):
                items.append({"code": "TRAINING_RECORDS", "message": "已读取训练记录", "count": len(records)})
        elif name == "get_today_workout":
            items.append({"code": "TRAINING_PLAN", "message": "已获取训练安排"})
        elif name == "get_current_training_cycle":
            items.append({"code": "TRAINING_CYCLE", "message": "已获取当前训练周期"})
        elif name == "get_runner_state":
            items.append({"code": "RUNNER_STATE", "message": "已获取当前训练状态"})
        elif name == "get_training_data_quality":
            if data.get("missing_fields") or data.get("missing_reasons"):
                items.append({"code": "DATA_PARTIAL", "message": "部分训练数据缺失"})
    if failures:
        items.append({"code": "FACTS_PARTIAL", "message": "部分训练数据暂未获取"})
    return items[:4]
