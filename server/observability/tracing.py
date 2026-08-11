"""Safe, optional request tracing for deterministic and Agent workflows.

This module intentionally contains no transport, persistence, or vendor SDK.
Applications may inject a :class:`TraceSink` (including a future OpenTelemetry
adapter), while a disabled tracer remains a no-op side channel.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Iterator, Protocol
from uuid import uuid4


logger = logging.getLogger(__name__)


# This is a whitelist, rather than a denylist: unknown metadata is never
# exported.  It keeps request content, identities, prompts, and credentials
# out of the trace boundary by construction.
SAFE_METADATA_KEYS = frozenset(
    {
        "intent",
        "tool_name",
        "graph_node",
        "validator_result",
        "fallback_reason",
        "provider_status",
        "knowledge_retrieval_status",
        "operation_type",
        "transport",
        "auth_status",
        "primitive",
        "resource_type",
        "result_count",
        "latency",
        "status",
        "error_code",
        "fallback",
        "provider_category",
        "provider_kind",
        "attempt",
        "max_attempts",
        "failure_category",
        "retried",
        "final_status",
        "retrieval_result_count",
        "proposal_id",
        "plan_count",
    }
)
# Kept as a public compatibility name for the v0.13 workflow integration.
SAFE_ATTRIBUTE_KEYS = SAFE_METADATA_KEYS
_SAFE_VALUE_TYPES = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class SpanRecord:
    """A transport-neutral, privacy-safe completed span.

    ``name`` and the three compatibility properties preserve the lightweight
    v0.13 API while new integrations use component/operation/metadata.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None
    component: str
    operation: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str
    error_code: str | None = None
    fallback: bool = False
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    name: str = ""

    @property
    def started_at(self) -> datetime:
        return self.start_time

    @property
    def ended_at(self) -> datetime:
        return self.end_time

    @property
    def latency_ms(self) -> float:
        return self.duration_ms

    @property
    def attributes(self) -> dict[str, str | int | float | bool | None]:
        return self.metadata


class TraceSink(Protocol):
    """Completed-span exporter boundary; an OpenTelemetry adapter can implement it."""

    def write(self, span: SpanRecord) -> None: ...


class InMemoryTraceSink:
    """Test-only sink with no external side effects."""

    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []

    def write(self, span: SpanRecord) -> None:
        self.spans.append(span)


class FanoutTraceSink:
    """Deliver a completed span to independent best-effort side channels."""

    def __init__(self, *sinks: TraceSink) -> None:
        self._sinks = tuple(sinks)

    def write(self, span: SpanRecord) -> None:
        for sink in self._sinks:
            try:
                sink.write(span)
            except Exception:
                logger.warning("trace_fanout_sink_failed code=TRACE_SINK_WRITE_FAILED")


@dataclass(frozen=True)
class TraceHandle:
    trace_id: str
    root_span_id: str


@dataclass
class ActiveSpan:
    """Mutable completion state exposed only within a ``with tracer.span`` block."""

    span_id: str
    _status: str = "SUCCEEDED"
    _error_code: str | None = None
    _fallback: bool = False
    _metadata: dict[str, object] = field(default_factory=dict)

    def set_status(self, status: str, *, error_code: str | None = None) -> None:
        self._status = status
        if error_code is not None:
            self._error_code = error_code

    def mark_error(self, error_code: str = "TRACE_OPERATION_FAILED") -> None:
        self.set_status("FAILED", error_code=error_code)

    def mark_fallback(self, reason: str | None = None) -> None:
        self._fallback = True
        if reason is not None:
            self._metadata["fallback_reason"] = reason

    def add_metadata(self, **metadata: object) -> None:
        self._metadata.update(metadata)


_ACTIVE_HANDLE: ContextVar[TraceHandle | None] = ContextVar("active_trace_handle", default=None)
_ACTIVE_SPAN_ID: ContextVar[str | None] = ContextVar("active_trace_span_id", default=None)
_ACTIVE_TRACER: ContextVar["SafeTracer | None"] = ContextVar("active_safe_tracer", default=None)


def active_trace_handle() -> TraceHandle | None:
    """Return request-local trace context, never request content or identity."""

    return _ACTIVE_HANDLE.get()


def active_tracer() -> "SafeTracer | None":
    """Return the request-local tracer for nested optional instrumentation."""

    return _ACTIVE_TRACER.get()


class SafeTracer:
    """Best-effort span writer that never changes a business request outcome."""

    def __init__(self, sink: TraceSink | None = None, enabled: bool = True) -> None:
        self.sink = sink
        self.enabled = enabled and sink is not None

    def start_trace(self) -> TraceHandle:
        return TraceHandle(trace_id=str(uuid4()), root_span_id=str(uuid4()))

    @staticmethod
    def _safe_metadata(metadata: dict[str, object] | None) -> dict[str, str | int | float | bool | None]:
        if not metadata:
            return {}
        safe: dict[str, str | int | float | bool | None] = {}
        for key, value in metadata.items():
            if key in SAFE_METADATA_KEYS and isinstance(value, _SAFE_VALUE_TYPES):
                safe[key] = value
        return safe

    @staticmethod
    def _parts(name: str | None, component: str | None, operation: str | None) -> tuple[str, str, str]:
        if component and operation:
            return component, operation, name or f"{component}.{operation}"
        value = name or "operation"
        if "." in value:
            parsed_component, parsed_operation = value.split(".", 1)
            return parsed_component, parsed_operation, value
        return "workflow", value, value

    @contextmanager
    def span(
        self,
        handle: TraceHandle,
        name: str | None = None,
        parent_span_id: str | None = None,
        *,
        component: str | None = None,
        operation: str | None = None,
        metadata: dict[str, object] | None = None,
        attributes: dict[str, object] | None = None,
        root: bool = False,
    ) -> Iterator[ActiveSpan]:
        """Capture one safe span and re-raise all business exceptions unchanged."""

        if not self.enabled:
            yield ActiveSpan(span_id="")
            return

        resolved_component, resolved_operation, resolved_name = self._parts(name, component, operation)
        span_id = handle.root_span_id if root else str(uuid4())
        parent = None if root else parent_span_id or _ACTIVE_SPAN_ID.get() or handle.root_span_id
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        state = ActiveSpan(span_id=span_id, _metadata={**(attributes or {}), **(metadata or {})})
        handle_token = _ACTIVE_HANDLE.set(handle)
        span_token = _ACTIVE_SPAN_ID.set(span_id)
        tracer_token = _ACTIVE_TRACER.set(self)
        try:
            yield state
        except Exception:
            if state._status == "SUCCEEDED":
                state.mark_error()
            raise
        finally:
            _ACTIVE_SPAN_ID.reset(span_token)
            _ACTIVE_HANDLE.reset(handle_token)
            _ACTIVE_TRACER.reset(tracer_token)
            ended_at = datetime.now(timezone.utc)
            record = SpanRecord(
                trace_id=handle.trace_id,
                span_id=span_id,
                parent_span_id=parent,
                component=resolved_component,
                operation=resolved_operation,
                start_time=started_at,
                end_time=ended_at,
                duration_ms=(perf_counter() - started) * 1000,
                status=state._status,
                error_code=state._error_code,
                fallback=state._fallback,
                metadata=self._safe_metadata(state._metadata),
                name=resolved_name,
            )
            try:
                assert self.sink is not None
                self.sink.write(record)
            except Exception:
                # Export is observability only.  Never let an exporter alter a
                # provider, validator, or transaction outcome.
                logger.warning("trace_sink_write_failed code=TRACE_SINK_WRITE_FAILED")

    @contextmanager
    def request(
        self,
        *,
        component: str,
        operation: str,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[TraceHandle]:
        """Create a root request span and make its context available to children."""

        handle = self.start_trace()
        with self.span(
            handle,
            component=component,
            operation=operation,
            metadata=metadata,
            root=True,
        ):
            yield handle


NOOP_TRACER = SafeTracer(enabled=False)
