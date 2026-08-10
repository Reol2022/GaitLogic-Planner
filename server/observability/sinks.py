"""Trace sink implementations kept outside Agent and workflow business code."""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

from server.observability.tracing import SAFE_METADATA_KEYS, SpanRecord

logger = logging.getLogger(__name__)

_SAFE_VALUE_TYPES = (str, int, float, bool, type(None))
_MAX_CACHED_ROOT_CONTEXTS = 256


class NoopTraceSink:
    """Explicit sink for enabled-but-not-exported tracing configurations."""

    def write(self, span: SpanRecord) -> None:
        del span


class OpenTelemetryUnavailableError(RuntimeError):
    """Raised only while optional OpenTelemetry infrastructure is initialized."""


class _OtelSpan(Protocol):
    def set_attribute(self, key: str, value: Any) -> None: ...

    def set_status(self, status: Any) -> None: ...

    def end(self, end_time: int | None = None) -> None: ...


class _OtelTracer(Protocol):
    def start_span(self, name: str, **kwargs: Any) -> _OtelSpan: ...


@dataclass(frozen=True)
class _OtelRuntime:
    tracer: _OtelTracer
    trace_api: Any
    status_class: Any
    status_code: Any


def _timestamp_ns(value) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _safe_attributes(span: SpanRecord) -> dict[str, str | int | float | bool]:
    """Map only already-safe internal fields to explicit OTel attributes."""

    attributes: dict[str, str | int | float | bool] = {
        "gaitlogic.trace_id": span.trace_id,
        "gaitlogic.span_id": span.span_id,
        "gaitlogic.component": span.component,
        "gaitlogic.operation": span.operation,
        "gaitlogic.duration_ms": span.duration_ms,
        "gaitlogic.status": span.status,
        "gaitlogic.fallback": span.fallback,
    }
    if span.parent_span_id is not None:
        attributes["gaitlogic.parent_span_id"] = span.parent_span_id
    if span.error_code is not None:
        attributes["gaitlogic.error_code"] = span.error_code
    for key, value in span.metadata.items():
        if value is not None and key in SAFE_METADATA_KEYS and isinstance(value, _SAFE_VALUE_TYPES):
            attributes[f"gaitlogic.metadata.{key}"] = value
    return attributes


class OpenTelemetryTraceSink:
    """Best-effort adapter from completed GaitLogic spans to OpenTelemetry.

    The internal sink receives spans at completion time, so it buffers normal
    child-first completion order until the root span arrives.  It then creates
    historical OTel spans parent-first.  A resumed HITL child can use a cached
    ended root context in the same process; after process restart we preserve
    the internal parent id as an attribute rather than inventing an OTel parent.
    """

    def __init__(self, runtime: _OtelRuntime) -> None:
        self._runtime = runtime
        self._pending: dict[str, dict[str, SpanRecord]] = {}
        self._exported_traces: OrderedDict[str, None] = OrderedDict()
        self._root_contexts: OrderedDict[tuple[str, str], _OtelSpan] = OrderedDict()
        self._lock = Lock()

    @classmethod
    def from_otlp(cls, *, endpoint: str, service_name: str = "gaitlogic-planner") -> "OpenTelemetryTraceSink":
        """Create an OTLP/HTTP exporter only when the optional SDK is installed."""

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.trace import Status, StatusCode
        except (ImportError, ModuleNotFoundError) as exc:
            raise OpenTelemetryUnavailableError("OTEL_SDK_UNAVAILABLE") from exc
        try:
            provider = TracerProvider()
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            runtime = _OtelRuntime(
                tracer=provider.get_tracer(service_name),
                trace_api=trace,
                status_class=Status,
                status_code=StatusCode,
            )
        except Exception as exc:
            raise OpenTelemetryUnavailableError("OTEL_EXPORTER_INITIALIZATION_FAILED") from exc
        return cls(runtime)

    @classmethod
    def for_test(cls, *, tracer: _OtelTracer, trace_api: Any, status_class: Any, status_code: Any) -> "OpenTelemetryTraceSink":
        """Build an adapter around a fake OTel runtime without a network collector."""

        return cls(
            _OtelRuntime(
                tracer=tracer,
                trace_api=trace_api,
                status_class=status_class,
                status_code=status_code,
            )
        )

    def write(self, span: SpanRecord) -> None:
        try:
            with self._lock:
                if span.trace_id in self._exported_traces:
                    self._emit(span, {})
                    return
                pending = self._pending.setdefault(span.trace_id, {})
                pending[span.span_id] = span
                if span.parent_span_id is None:
                    self._flush_trace(span.trace_id)
        except Exception:
            # No exporter exception can cross the TraceSink boundary.
            logger.warning("otel_trace_export_failed code=OTEL_EXPORT_FAILED")

    def _flush_trace(self, trace_id: str) -> None:
        records = self._pending.pop(trace_id, {})
        emitted: dict[str, _OtelSpan] = {}
        remaining = dict(records)
        while remaining:
            ready = [
                item
                for item in remaining.values()
                if item.parent_span_id is None or item.parent_span_id in emitted or (trace_id, item.parent_span_id) in self._root_contexts
            ]
            if not ready:
                # The internal parent was not available (for example a resumed
                # process).  Preserve the safe parent id attribute but do not
                # fabricate an SDK context.
                ready = list(remaining.values())
            for item in ready:
                emitted[item.span_id] = self._emit(item, emitted)
                del remaining[item.span_id]
        self._exported_traces[trace_id] = None
        self._exported_traces.move_to_end(trace_id)
        while len(self._exported_traces) > _MAX_CACHED_ROOT_CONTEXTS:
            self._exported_traces.popitem(last=False)

    def _emit(self, record: SpanRecord, emitted: dict[str, _OtelSpan]) -> _OtelSpan:
        parent = emitted.get(record.parent_span_id or "")
        if parent is None and record.parent_span_id is not None:
            parent = self._root_contexts.get((record.trace_id, record.parent_span_id))
        kwargs: dict[str, Any] = {
            "attributes": _safe_attributes(record),
            "start_time": _timestamp_ns(record.start_time),
        }
        if parent is not None:
            kwargs["context"] = self._runtime.trace_api.set_span_in_context(parent)
        otel_span = self._runtime.tracer.start_span(
            f"{record.component}.{record.operation}",
            **kwargs,
        )
        if record.status == "FAILED":
            otel_span.set_status(
                self._runtime.status_class(
                    self._runtime.status_code.ERROR,
                    record.error_code or "TRACE_OPERATION_FAILED",
                )
            )
        elif record.status == "SUCCEEDED":
            otel_span.set_status(self._runtime.status_class(self._runtime.status_code.OK))
        otel_span.end(end_time=_timestamp_ns(record.end_time))
        if record.parent_span_id is None:
            self._root_contexts[(record.trace_id, record.span_id)] = otel_span
            self._root_contexts.move_to_end((record.trace_id, record.span_id))
            while len(self._root_contexts) > _MAX_CACHED_ROOT_CONTEXTS:
                self._root_contexts.popitem(last=False)
        return otel_span
