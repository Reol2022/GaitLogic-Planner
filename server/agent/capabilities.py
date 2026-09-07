"""Capability runtime primitives.

Tools remain small read-only fact readers.  Skills use the same external
tool-calling contract, but may orchestrate several tools or an existing
workflow.  This module deliberately does not contain domain decisions.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from server.agent.schemas import AgentToolResult


class CapabilityKind(str, Enum):
    TOOL = "tool"
    SKILL = "skill"


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    kind: CapabilityKind
    required_capabilities: tuple[str, ...] = ()
    optional_capabilities: tuple[str, ...] = ()
    cacheable: bool = True
    visible_to_model: bool = True


@dataclass
class ExecutionContext:
    """Request-scoped execution state; never persisted or put in prompts."""

    results: dict[str, AgentToolResult] = field(default_factory=dict)
    executed_capabilities: set[str] = field(default_factory=set)

    @staticmethod
    def cache_key(name: str, arguments: dict) -> str:
        return f"{name}:{json.dumps(arguments, sort_keys=True, ensure_ascii=True, separators=(',', ':'))}"

    def get(self, name: str, arguments: dict) -> AgentToolResult | None:
        return self.results.get(self.cache_key(name, arguments))

    def put(self, name: str, arguments: dict, result: AgentToolResult) -> None:
        self.executed_capabilities.add(name)
        if result.status.value == "SUCCEEDED":
            self.results[self.cache_key(name, arguments)] = result

    def clear_after_write(self) -> None:
        self.results.clear()


_execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "gaitlogic_capability_execution_context", default=None
)


def active_execution_context() -> ExecutionContext | None:
    return _execution_context.get()


@contextmanager
def execution_context_scope(context: ExecutionContext | None = None) -> Iterator[ExecutionContext]:
    runtime = context or ExecutionContext()
    token = _execution_context.set(runtime)
    try:
        yield runtime
    finally:
        _execution_context.reset(token)
