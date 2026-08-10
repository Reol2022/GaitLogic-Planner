"""Configuration-only composition for optional trace exporters."""

from __future__ import annotations

import logging
from functools import lru_cache

from planner_core.config import Settings, get_settings
from server.observability.metrics import (
    InMemoryMetricsSink,
    MetricsRecorder,
    MetricsTraceSink,
    NoopMetricsSink,
)
from server.observability.sinks import (
    NoopTraceSink,
    OpenTelemetryTraceSink,
    OpenTelemetryUnavailableError,
)
from server.observability.tracing import FanoutTraceSink, NOOP_TRACER, SafeTracer, TraceSink

logger = logging.getLogger(__name__)


class TraceConfigurationError(ValueError):
    """A safe configuration classification, never containing raw values."""


def build_trace_sink(settings: Settings) -> TraceSink:
    if settings.agent_trace_exporter == "noop":
        return NoopTraceSink()
    if settings.agent_trace_exporter == "otlp":
        if not settings.otel_exporter_otlp_endpoint:
            raise TraceConfigurationError("OTEL_ENDPOINT_MISSING")
        return OpenTelemetryTraceSink.from_otlp(
            endpoint=settings.otel_exporter_otlp_endpoint,
        )
    raise TraceConfigurationError("TRACE_EXPORTER_UNSUPPORTED")


def build_metrics_recorder(settings: Settings) -> MetricsRecorder:
    """Build bounded local metrics only; no external metrics exporter is required."""

    if not settings.agent_metrics_enabled:
        return MetricsRecorder(NoopMetricsSink(), enabled=False)
    return MetricsRecorder(
        InMemoryMetricsSink(max_latency_samples=settings.agent_metrics_max_latency_samples),
    )


def build_configured_tracer(settings: Settings) -> SafeTracer:
    """Compose optional trace export and bounded metrics without business coupling."""

    sinks: list[TraceSink] = []
    if settings.agent_tracing_enabled:
        try:
            sinks.append(build_trace_sink(settings))
        except (TraceConfigurationError, OpenTelemetryUnavailableError):
            logger.warning("agent_trace_exporter_disabled code=TRACE_EXPORTER_UNAVAILABLE")
    recorder = build_metrics_recorder(settings)
    if recorder.enabled:
        sinks.append(MetricsTraceSink(recorder))
    if not sinks:
        return NOOP_TRACER
    return SafeTracer(FanoutTraceSink(*sinks))


@lru_cache(maxsize=1)
def get_configured_tracer() -> SafeTracer:
    return build_configured_tracer(get_settings())
