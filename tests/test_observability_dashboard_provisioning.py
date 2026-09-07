import json
from pathlib import Path


ROOT = Path("deploy/observability")


def test_dashboard_uids_are_valid_and_stable() -> None:
    expected = {
        "agent-overview.json": "gaitlogic-agent-overview",
        "rag-observability.json": "gaitlogic-rag-observability",
        "safety-decisions.json": "gaitlogic-safety-decisions",
        "evaluation-analysis.json": "gaitlogic-evaluation-analysis",
    }
    for filename, uid in expected.items():
        payload = json.loads((ROOT / "grafana/dashboards" / filename).read_text(encoding="utf-8"))
        assert payload["uid"] == uid
        assert payload["panels"]


def test_datasource_provisioning_uses_container_hosts_and_stable_uids() -> None:
    content = (ROOT / "grafana/provisioning/datasources/gaitlogic.yaml").read_text(encoding="utf-8")
    for uid in ("gaitlogic-prometheus", "gaitlogic-tempo", "gaitlogic-jaeger"):
        assert f"uid: {uid}" in content
    assert "http://localhost" not in content
