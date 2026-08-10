from __future__ import annotations

from datetime import date

import pytest

from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import PlannedSessionFact, WeeklyFactsRequest, WeeklyPeriod, WorkoutSessionFact
from server.observability.tracing import InMemoryTraceSink, SafeTracer
from server.weekly_review_graph.schemas import WeeklyReviewDraft, WeeklyReviewState
from server.weekly_review_graph.workflow import build_weekly_review_graph


def facts():
    day = date(2026, 7, 6)
    return build_weekly_facts(
        period=WeeklyPeriod(week_start=day, week_end=date(2026, 7, 12), timezone="Asia/Shanghai"),
        plans=[PlannedSessionFact(plan_id=1, session_date=day, main_type="easy", distance_km=8)],
        logs=[WorkoutSessionFact(log_id=1, planned_workout_id=1, activity_date=day, main_type="easy", distance_km=8, duration_minutes=48, status="completed_normal")],
        runner_state_samples=[],
        as_of_date=date(2026, 7, 12),
    )


def draft():
    return WeeklyReviewDraft(
        overview="虚构概况",
        completion_summary="虚构完成情况",
        key_session_summary="虚构关键课摘要",
        deviation_summary="虚构偏差摘要",
        fatigue_and_risk="数据不足，不作额外推断。",
        next_week_focus=["人工复核"],
    )


def test_weekly_graph_emits_rooted_safe_spans_with_graph_nodes() -> None:
    sink = InMemoryTraceSink()
    tracer = SafeTracer(sink)
    graph = build_weekly_review_graph(
        facts_loader=lambda request: facts(),
        generator=lambda state: draft(),
        tracer=tracer,
    )
    request = WeeklyFactsRequest(user_id=7, week_start=date(2026, 7, 6), week_end=date(2026, 7, 12))
    result = graph.invoke(WeeklyReviewState(user_id=7, request=request).model_dump(mode="python"))
    assert result["final_review"] is not None
    assert {item.name for item in sink.spans} == {
        "langgraph.weekly_review",
        "weekly_facts", "rules.evaluate", "rag.retrieve", "llm.generate", "validator", "finalize"
    }
    assert len({item.span_id for item in sink.spans}) == len(sink.spans)
    assert len({item.trace_id for item in sink.spans}) == 1
    root = next(item for item in sink.spans if item.name == "langgraph.weekly_review")
    assert root.parent_span_id is None
    assert all(
        item.parent_span_id == root.span_id
        for item in sink.spans
        if item is not root
    )
    assert all(
        item.metadata.get("graph_node") == item.name
        for item in sink.spans
        if item is not root
    )
    serialized = str([item.attributes for item in sink.spans]).lower()
    assert "prompt" not in serialized
    assert "api_key" not in serialized


def test_tracing_disabled_does_not_change_business_result() -> None:
    graph = build_weekly_review_graph(
        facts_loader=lambda request: facts(),
        generator=lambda state: draft(),
        tracer=SafeTracer(enabled=False),
    )
    request = WeeklyFactsRequest(user_id=7, week_start=date(2026, 7, 6), week_end=date(2026, 7, 12))
    assert graph.invoke(WeeklyReviewState(user_id=7, request=request).model_dump(mode="python"))["final_review"] is not None


def test_sink_failure_is_non_blocking() -> None:
    class BrokenSink:
        def write(self, span):
            raise RuntimeError("fictional sink failure")

    tracer = SafeTracer(BrokenSink())
    handle = tracer.start_trace()
    with tracer.span(handle, "validator", attributes={"prompt": "must-be-dropped"}):
        value = 1
    assert value == 1


def test_span_records_error_and_reraises_business_exception() -> None:
    sink = InMemoryTraceSink()
    tracer = SafeTracer(sink)
    with pytest.raises(ValueError):
        with tracer.span(tracer.start_trace(), "llm.generate"):
            raise ValueError("fictional provider failure")
    assert sink.spans[0].status == "FAILED"
