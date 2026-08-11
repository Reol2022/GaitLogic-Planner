"""Privacy-safe, transport-neutral runtime metrics derived from completed spans.

Metrics deliberately aggregate only a small allowlist of dimensions.  They do
not retain trace identifiers, request bodies, model output, or user data.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import logging
from math import ceil
from threading import Lock
from typing import Protocol

from server.observability.tracing import SpanRecord, TraceSink


logger = logging.getLogger(__name__)

SAFE_METRIC_LABELS = frozenset(
    {
        "component",
        "operation",
        "tool_name",
        "provider_kind",
        "failure_category",
        "status",
        "fallback",
        "transport",
        "auth_status",
        "primitive",
        "resource_type",
        "vector_store",
        "retrieval_strategy",
        "fusion_method",
        "reranker",
        "model_family",
    }
)
_SAFE_LABEL_VALUE_TYPES = (str, int, float, bool)


@dataclass(frozen=True)
class MetricPoint:
    """One already-aggregatable metric observation without request identity."""

    name: str
    value: float
    labels: tuple[tuple[str, str], ...] = ()
    kind: str = "counter"


class MetricsSink(Protocol):
    """Internal metrics export boundary; implementations must be side-effect safe."""

    def record(self, point: MetricPoint) -> None: ...


class NoopMetricsSink:
    def record(self, point: MetricPoint) -> None:
        del point


class InMemoryMetricsSink:
    """Bounded aggregate sink for tests and small local deployments.

    Only latency samples are retained and each metric/label series has a fixed
    cap.  Counters remain aggregates, so it never stores raw spans.
    """

    def __init__(self, *, max_latency_samples: int = 2048) -> None:
        if max_latency_samples < 1:
            raise ValueError("max_latency_samples must be positive")
        self._max_latency_samples = max_latency_samples
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._latencies: dict[tuple[str, tuple[tuple[str, str], ...]], deque[float]] = {}
        self._lock = Lock()

    def record(self, point: MetricPoint) -> None:
        key = (point.name, point.labels)
        with self._lock:
            if point.kind == "counter":
                self._counters[key] += point.value
            elif point.kind == "latency":
                values = self._latencies.setdefault(key, deque(maxlen=self._max_latency_samples))
                values.append(point.value)
            else:
                raise ValueError("METRIC_KIND_UNSUPPORTED")

    @staticmethod
    def _labels(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((labels or {}).items()))

    def counter(self, name: str, *, labels: dict[str, str] | None = None) -> float:
        with self._lock:
            if labels is None:
                return sum(value for (metric_name, _), value in self._counters.items() if metric_name == name)
            return self._counters.get((name, self._labels(labels)), 0.0)

    def latency_count(self, name: str, *, labels: dict[str, str] | None = None) -> int:
        with self._lock:
            if labels is None:
                return sum(len(values) for (metric_name, _), values in self._latencies.items() if metric_name == name)
            return len(self._latencies.get((name, self._labels(labels)), ()))

    def percentile(self, name: str, percentile: int, *, labels: dict[str, str] | None = None) -> float | None:
        if percentile not in {50, 95}:
            raise ValueError("METRIC_PERCENTILE_UNSUPPORTED")
        with self._lock:
            values = sorted(self._latencies.get((name, self._labels(labels)), ()))
        if not values:
            return None
        # Nearest-rank is deterministic and has no dependency on a monitoring SDK.
        return values[max(0, ceil((percentile / 100) * len(values)) - 1)]


class MetricsRecorder:
    """Best-effort metrics derivation that never changes business outcomes."""

    def __init__(self, sink: MetricsSink | None = None, *, enabled: bool = True) -> None:
        self.sink = sink
        self.enabled = enabled and sink is not None

    @staticmethod
    def _labels(span: SpanRecord) -> dict[str, str]:
        labels: dict[str, str] = {
            "component": span.component,
            "operation": span.operation,
            "status": span.status,
            "fallback": str(span.fallback).lower(),
        }
        for key in ("tool_name", "provider_kind", "failure_category", "transport", "auth_status", "primitive", "resource_type", "vector_store", "retrieval_strategy", "fusion_method", "reranker", "model_family"):
            value = span.metadata.get(key)
            if key in SAFE_METRIC_LABELS and isinstance(value, _SAFE_LABEL_VALUE_TYPES):
                labels[key] = str(value)
        return labels

    def _record(self, name: str, value: float, labels: dict[str, str], *, kind: str = "counter") -> None:
        if not self.enabled:
            return
        safe_labels = tuple(sorted((key, value) for key, value in labels.items() if key in SAFE_METRIC_LABELS))
        try:
            assert self.sink is not None
            self.sink.record(MetricPoint(name=name, value=value, labels=safe_labels, kind=kind))
        except Exception:
            logger.warning("metrics_sink_record_failed code=METRICS_SINK_WRITE_FAILED")

    def record_span(self, span: SpanRecord) -> None:
        """Derive only metrics that the current completed span actually supports."""

        if not self.enabled:
            return
        labels = self._labels(span)
        success = span.status == "SUCCEEDED"

        if span.component == "coach_api" and span.operation == "query":
            self._record("agent_request_count", 1, labels)
            self._record("agent_success_count" if success else "agent_failure_count", 1, labels)
            self._record("agent_total_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "mcp.http" and span.operation == "request":
            self._record("mcp_http_request_count", 1, labels)
            if span.metadata.get("failure_category") == "INVALID_ORIGIN":
                self._record("mcp_origin_reject", 1, labels)
        elif span.component == "auth" and span.operation == "validate":
            self._record("mcp_auth_success" if success else "mcp_auth_failure", 1, labels)
        elif span.component == "mcp" and span.operation == "tool":
            self._record("mcp_tool_call_count", 1, labels)
            self._record("mcp_tool_success" if success else "mcp_tool_failure", 1, labels)
            self._record("mcp_tool_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "mcp" and span.operation == "resource":
            self._record("mcp_resource_read_count", 1, labels)
            self._record("mcp_resource_success" if success else "mcp_resource_failure", 1, labels)
        elif span.component == "mcp" and span.operation == "prompt":
            self._record("mcp_prompt_get_count", 1, labels)
        elif span.component == "tool" and span.operation == "invoke":
            self._record("tool_call_count", 1, labels)
            self._record("tool_success_count" if success else "tool_failure_count", 1, labels)
            self._record("tool_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "knowledge" and span.operation == "retrieve":
            self._record("retrieval_count", 1, labels)
            self._record("retrieval_success" if success else "retrieval_failure", 1, labels)
            self._record("retrieval_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "knowledge" and span.operation == "vector_search":
            self._record("vector_store_query_count", 1, labels)
            self._record(
                "vector_store_query_success" if success else "vector_store_query_failure",
                1,
                labels,
            )
            self._record(
                "vector_store_query_latency_ms",
                span.duration_ms,
                labels,
                kind="latency",
            )
        elif span.component == "knowledge" and span.operation == "sparse_search":
            self._record("retrieval_query_count", 1, labels)
            self._record("retrieval_success" if success else "retrieval_failure", 1, labels)
            self._record("retrieval_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "knowledge" and span.operation == "hybrid_retrieval":
            self._record("retrieval_query_count", 1, labels)
            self._record("retrieval_success" if success else "retrieval_failure", 1, labels)
            self._record("retrieval_latency_ms", span.duration_ms, labels, kind="latency")
            self._record("hybrid_fusion_latency_ms", span.duration_ms, labels, kind="latency")
        elif span.component == "knowledge" and span.operation == "rerank":
            self._record("reranker_request_count", 1, labels)
            self._record("reranker_success" if success else "reranker_failure", 1, labels)
            self._record("reranker_latency_ms", span.duration_ms, labels, kind="latency")
            if span.fallback:
                self._record("reranker_fallback_count", 1, labels)
        elif span.component == "provider" and span.operation == "rerank":
            attempts = span.metadata.get("attempt")
            if isinstance(attempts, int) and attempts > 1:
                self._record("reranker_retry_count", attempts - 1, labels)
        elif span.component == "provider" and span.operation == "generate":
            self._record("provider_request_count", 1, labels)
            self._record("provider_success" if success else "provider_failure", 1, labels)
            self._record("provider_latency_ms", span.duration_ms, labels, kind="latency")
            attempts = span.metadata.get("attempt")
            if isinstance(attempts, int) and attempts > 0:
                self._record("provider_attempts", attempts, labels)
                if attempts > 1:
                    self._record("provider_retry_count", attempts - 1, labels)
            category = span.metadata.get("failure_category")
            if category == "PROVIDER_TIMEOUT":
                self._record("provider_timeout_count", 1, labels)
            elif category == "PROVIDER_RATE_LIMIT":
                self._record("provider_rate_limit_count", 1, labels)
        elif span.component == "validator":
            self._record("validator_pass" if success else "validator_reject", 1, labels)
        elif span.component == "fallback" or span.fallback:
            self._record("fallback_count", 1, labels)
            if span.metadata.get("fallback_reason") == "WEEKLY_REVIEW_VALIDATION_FALLBACK":
                self._record("weekly_review_fallback", 1, labels)
        elif span.component == "langgraph" and span.operation == "weekly_review":
            self._record("weekly_review_success" if success else "weekly_review_failure", 1, labels)
        elif span.component == "approval" and span.operation == "approve_proposal":
            self._record("proposal_approve", 1, labels)
            self._record("proposal_apply_success" if success else "proposal_apply_failure", 1, labels)
        elif span.component == "approval" and span.operation == "reject_proposal":
            self._record("proposal_reject", 1, labels)


class MetricsTraceSink:
    """Adapter so runtime metrics are a passive completed-span side channel."""

    def __init__(self, recorder: MetricsRecorder) -> None:
        self.recorder = recorder

    def write(self, span: SpanRecord) -> None:
        self.recorder.record_span(span)
