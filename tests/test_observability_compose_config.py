from pathlib import Path

import yaml


ROOT = Path("deploy/observability")


def test_local_stack_binds_published_ports_to_loopback_only() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"otel-collector", "prometheus", "tempo", "jaeger", "grafana"} <= set(services)
    for service in services.values():
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:")
    assert ":latest" not in (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_collector_keeps_otlp_ingress_and_trace_metric_fanout() -> None:
    collector = yaml.safe_load((ROOT / "otel-collector.yaml").read_text(encoding="utf-8"))
    assert {"grpc", "http"} <= set(collector["receivers"]["otlp"]["protocols"])
    assert collector["service"]["pipelines"]["traces"]["exporters"] == ["otlp/tempo", "otlp/jaeger"]
    assert collector["service"]["pipelines"]["metrics"]["exporters"] == ["prometheus"]
