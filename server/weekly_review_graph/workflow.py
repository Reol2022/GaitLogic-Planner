from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from server.weekly_review_graph.nodes import WeeklyReviewNodes
from server.weekly_review_graph.ports import (
    WeeklyFactsLoader,
    WeeklyKnowledgeRetriever,
    WeeklyReviewGenerator,
)
from server.weekly_review_graph.schemas import WeeklyReviewGraphStatus, WeeklyReviewState
from server.observability.tracing import NOOP_TRACER, SafeTracer, TraceHandle


class _TracedWeeklyReviewGraph:
    """Keep the root span open across every synchronous LangGraph node."""

    def __init__(self, graph: Any, tracer: SafeTracer) -> None:
        self._graph = graph
        self._tracer = tracer

    def invoke(self, raw: WeeklyReviewState | dict, *args: Any, **kwargs: Any):
        state = raw if isinstance(raw, WeeklyReviewState) else WeeklyReviewState.model_validate(raw)
        if state.trace_context.get("trace_id") and state.trace_context.get("root_span_id"):
            return self._graph.invoke(raw, *args, **kwargs)
        handle = self._tracer.start_trace()
        values = state.model_dump(mode="python")
        values["trace_context"] = {
            "trace_id": handle.trace_id,
            "root_span_id": handle.root_span_id,
        }
        with self._tracer.span(
            handle,
            component="langgraph",
            operation="weekly_review",
            metadata={"operation_type": "weekly_review_graph"},
            root=True,
        ):
            return self._graph.invoke(values, *args, **kwargs)

    def get_graph(self, *args: Any, **kwargs: Any):
        return self._graph.get_graph(*args, **kwargs)


def _after_validation(state: WeeklyReviewState | dict) -> str:
    value = state if isinstance(state, WeeklyReviewState) else WeeklyReviewState.model_validate(state)
    return "fallback_weekly_review" if value.status == WeeklyReviewGraphStatus.FALLBACK else "finalize_weekly_review"


def build_weekly_review_graph(
    *,
    facts_loader: WeeklyFactsLoader,
    generator: WeeklyReviewGenerator,
    knowledge_retriever: WeeklyKnowledgeRetriever | None = None,
    tracer: SafeTracer | None = None,
):
    tracer = tracer or NOOP_TRACER
    nodes = WeeklyReviewNodes(
        facts_loader=facts_loader,
        generator=generator,
        knowledge_retriever=knowledge_retriever,
    )
    def traced(name, function):
        def run(raw):
            state = raw if isinstance(raw, WeeklyReviewState) else WeeklyReviewState.model_validate(raw)
            values = state.trace_context
            handle = (
                TraceHandle(trace_id=values["trace_id"], root_span_id=values["root_span_id"])
                if values.get("trace_id") and values.get("root_span_id")
                else tracer.start_trace()
            )
            is_root = name == "weekly_facts" and not values.get("root_span_id")
            with tracer.span(
                handle,
                name,
                metadata={"graph_node": name},
                root=is_root,
            ) as span:
                if name == "fallback":
                    span.mark_fallback("WEEKLY_REVIEW_VALIDATION_FALLBACK")
                result = function(raw)
            if name == "weekly_facts":
                result["trace_context"] = {
                    "trace_id": handle.trace_id,
                    "root_span_id": handle.root_span_id,
                }
            return result
        return run

    graph = StateGraph(WeeklyReviewState)
    graph.add_node("load_weekly_facts", traced("weekly_facts", nodes.load_weekly_facts))
    graph.add_node("evaluate_weekly_rules", traced("rules.evaluate", nodes.evaluate_weekly_rules))
    graph.add_node("retrieve_training_knowledge", traced("rag.retrieve", nodes.retrieve_training_knowledge))
    graph.add_node("generate_weekly_review", traced("llm.generate", nodes.generate_weekly_review))
    graph.add_node("validate_weekly_review", traced("validator", nodes.validate_weekly_review))
    graph.add_node("fallback_weekly_review", traced("fallback", nodes.fallback_weekly_review))
    graph.add_node("finalize_weekly_review", traced("finalize", nodes.finalize_weekly_review))
    graph.add_edge(START, "load_weekly_facts")
    graph.add_edge("load_weekly_facts", "evaluate_weekly_rules")
    graph.add_edge("evaluate_weekly_rules", "retrieve_training_knowledge")
    graph.add_edge("retrieve_training_knowledge", "generate_weekly_review")
    graph.add_edge("generate_weekly_review", "validate_weekly_review")
    graph.add_conditional_edges(
        "validate_weekly_review",
        _after_validation,
        {
            "fallback_weekly_review": "fallback_weekly_review",
            "finalize_weekly_review": "finalize_weekly_review",
        },
    )
    graph.add_edge("fallback_weekly_review", "finalize_weekly_review")
    graph.add_edge("finalize_weekly_review", END)
    return _TracedWeeklyReviewGraph(graph.compile(), tracer)
