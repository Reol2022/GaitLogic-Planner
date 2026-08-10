from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from server.observability.tracing import NOOP_TRACER, SafeTracer, TraceHandle


class AdaptiveApprovalState(TypedDict):
    user_id: int
    proposal_id: int
    decision: str | None
    trace_context: dict[str, str]


class _TracedAdaptiveApprovalGraph:
    """Propagate only random trace identifiers through HITL checkpoints.

    A resumed approval is a later request, so it creates a new child Span using
    the persisted internal root id.  It does not pretend that an SDK context
    survived a process restart.
    """

    def __init__(self, graph: Any, tracer: SafeTracer) -> None:
        self._graph = graph
        self._tracer = tracer

    @staticmethod
    def _handle(values: dict[str, Any] | None) -> TraceHandle | None:
        context = (values or {}).get("trace_context") or {}
        trace_id = context.get("trace_id")
        root_span_id = context.get("root_span_id")
        if isinstance(trace_id, str) and isinstance(root_span_id, str):
            return TraceHandle(trace_id=trace_id, root_span_id=root_span_id)
        return None

    def invoke(self, payload: Any, config: dict | None = None, *args: Any, **kwargs: Any):
        if isinstance(payload, dict):
            handle = self._handle(payload) or self._tracer.start_trace()
            values = dict(payload)
            values["trace_context"] = {
                "trace_id": handle.trace_id,
                "root_span_id": handle.root_span_id,
            }
            with self._tracer.span(
                handle,
                component="hitl",
                operation="await_approval",
                metadata={"operation_type": "human_approval"},
                root=not bool(self._handle(payload)),
            ):
                return self._graph.invoke(values, config, *args, **kwargs)

        checkpoint = self._graph.get_state(config or {})
        values = getattr(checkpoint, "values", None)
        handle = self._handle(values)
        if handle is None:
            return self._graph.invoke(payload, config, *args, **kwargs)
        with self._tracer.span(
            handle,
            component="hitl",
            operation="resume_approval",
            parent_span_id=handle.root_span_id,
            metadata={"operation_type": "human_approval_resume"},
        ):
            return self._graph.invoke(payload, config, *args, **kwargs)

    def get_graph(self, *args: Any, **kwargs: Any):
        return self._graph.get_graph(*args, **kwargs)


def request_human_approval(state: AdaptiveApprovalState) -> dict:
    decision = interrupt(
        {
            "proposal_id": state["proposal_id"],
            "allowed_actions": ["approve", "reject"],
        }
    )
    if decision not in {"approve", "reject"}:
        raise ValueError("Human decision must be approve or reject")
    return {"decision": decision}


def build_adaptive_approval_graph(*, checkpointer, tracer: SafeTracer | None = None):
    graph = StateGraph(AdaptiveApprovalState)
    graph.add_node("human_interrupt", request_human_approval)
    graph.add_edge(START, "human_interrupt")
    graph.add_edge("human_interrupt", END)
    return _TracedAdaptiveApprovalGraph(graph.compile(checkpointer=checkpointer), tracer or NOOP_TRACER)
