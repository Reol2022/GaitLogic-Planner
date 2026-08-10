from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Iterator, Protocol
from uuid import uuid4


SAFE_ATTRIBUTE_KEYS = frozenset(
    {
        "intent",
        "status",
        "error_code",
        "tool_name",
        "retrieval_result_count",
        "validator_result",
        "fallback",
        "provider_category",
        "proposal_id",
        "plan_count",
    }
)


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    status: str
    attributes: dict[str, str | int | float | bool | None] = field(default_factory=dict)


class TraceSink(Protocol):
    def write(self, span: SpanRecord) -> None: ...


class InMemoryTraceSink:
    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []

    def write(self, span: SpanRecord) -> None:
        self.spans.append(span)


@dataclass(frozen=True)
class TraceHandle:
    trace_id: str
    root_span_id: str


class SafeTracer:
    """Failure-isolated tracing with an OpenTelemetry-shaped span model."""

    def __init__(self, sink: TraceSink | None = None, *, enabled: bool = True) -> None:
        self.sink = sink
        self.enabled = enabled and sink is not None

    def start_trace(self) -> TraceHandle:
        return TraceHandle(trace_id=str(uuid4()), root_span_id=str(uuid4()))

    @contextmanager
    def span(
        self,
        handle: TraceHandle,
        name: str,
        *,
        parent_span_id: str | None = None,
        attributes: dict[str, str | int | float | bool | None] | None = None,
    ) -> Iterator[str]:
        span_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        status = "SUCCEEDED"
        safe = {
            key: value
            for key, value in (attributes or {}).items()
            if key in SAFE_ATTRIBUTE_KEYS
        }
        try:
            yield span_id
        except Exception:
            status = "FAILED"
            raise
        finally:
            if self.enabled:
                record = SpanRecord(
                    trace_id=handle.trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id or handle.root_span_id,
                    name=name,
                    started_at=started_at,
                    ended_at=datetime.now(timezone.utc),
                    latency_ms=round((perf_counter() - started) * 1000, 3),
                    status=status,
                    attributes=safe,
                )
                try:
                    self.sink.write(record)
                except Exception:
                    pass


NOOP_TRACER = SafeTracer(enabled=False)
