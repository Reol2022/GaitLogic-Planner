#!/usr/bin/env python3
"""Best-effort local stack smoke test; it never calls a real LLM provider."""

from __future__ import annotations

import json
import time
from urllib.parse import quote
from urllib.request import urlopen

from server.observability.sinks import OpenTelemetryTraceSink
from server.observability.tracing import SafeTracer


def get(url: str) -> str:
    with urlopen(url, timeout=5) as response:  # nosec B310 - fixed local URLs
        return response.read().decode()


def main() -> None:
    checks = {
        "Collector": "http://127.0.0.1:9464/metrics",
        "Tempo": "http://127.0.0.1:3200/ready",
        "Jaeger": "http://127.0.0.1:16686/",
        "Prometheus": "http://127.0.0.1:9090/-/ready",
        "Grafana": "http://127.0.0.1:3000/api/health",
    }
    for name, url in checks.items():
        get(url)
        print(f"{name}: healthy")
    tracer = SafeTracer(OpenTelemetryTraceSink.from_otlp(
        endpoint="http://127.0.0.1:4318/v1/traces", service_name="gaitlogic-planner"
    ))
    with tracer.request(component="http", operation="request", metadata={"http_method": "GET"}) as handle:
        with tracer.span(handle, component="coach_api", operation="query", metadata={"intent": "SMOKE_TEST"}):
            with tracer.span(handle, component="decision", operation="outcome", metadata={"decision_outcome": "full_answer", "decision_source": "smoke_test"}):
                pass
    time.sleep(6)
    query = quote('gaitlogic_answers_total_total{decision_outcome="full_answer"}')
    metric = json.loads(get(f"http://127.0.0.1:9090/api/v1/query?query={query}"))
    if metric.get("status") != "success" or not metric.get("data", {}).get("result"):
        raise RuntimeError("Prometheus did not receive the smoke metric")
    print("Metrics: received")
    print("Trace fanout: exported to Collector; query the emitted trace in Tempo and Jaeger by service=gaitlogic-planner")
    print("Evaluation metrics: " + ("available" if "gaitlogic_eval_fact_consistency" in get("http://127.0.0.1:9090/api/v1/label/__name__/values") else "check Prometheus target"))


if __name__ == "__main__":
    main()
