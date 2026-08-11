"""Unified, offline regression orchestration for public Agent evaluations.

Imports are deliberately lazy: MCP evaluation imports the public result schema,
while the registry imports MCP evaluation.  Eager package exports would create a
cycle before either implementation can run.
"""

from typing import Any

__all__ = ["EvaluationRegistry", "UnifiedEvaluationRunner"]


def __getattr__(name: str) -> Any:
    if name == "EvaluationRegistry":
        from server.agent.evaluation_regression.registry import EvaluationRegistry
        return EvaluationRegistry
    if name == "UnifiedEvaluationRunner":
        from server.agent.evaluation_regression.runner import UnifiedEvaluationRunner
        return UnifiedEvaluationRunner
    raise AttributeError(name)
