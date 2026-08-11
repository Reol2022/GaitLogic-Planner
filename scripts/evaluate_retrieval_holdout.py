"""Run the frozen public retrieval holdout without exporting private content."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings
from server.knowledge_retrieval.evaluation.holdout import run_holdout

DATASET = ROOT / "docs/evaluation/datasets/retrieval-holdout-v2.json"
OUTPUT = ROOT / "docs/evaluation/reports/retrieval-holdout-v2.json"
MARKDOWN = ROOT / "docs/evaluation/reports/retrieval-holdout-v2.md"


def _markdown(report: dict[str, object]) -> str:
    rows = []
    for name, value in report["strategies"].items():
        metrics = value.get("metrics", {})
        rows.append(f"| {name} | {value.get('status')} | {value.get('passed_cases', 'N/A')}/{value.get('case_count', 'N/A')} | {metrics.get('recall_at_4', 'N/A')} | {metrics.get('mrr_at_4', 'N/A')} | {metrics.get('ndcg_at_4', 'N/A')} | {metrics.get('forbidden_document_rate', 'N/A')} | {metrics.get('filter_violation_rate', 'N/A')} | {metrics.get('p50_latency_ms', 'N/A')}/{metrics.get('p95_latency_ms', 'N/A')} |")
    return "\n".join(["# Retrieval Holdout v2", "", "Independent public fictional holdout. Reports deliberately omit query text, chunks, vectors and provider payloads.", "", f"- Dataset SHA-256: `{report['dataset_sha256']}`", f"- Case count: {report['case_count']}", "", "| Strategy | Status | Pass | Recall@4 | MRR@4 | nDCG@4 | Forbidden | Filter violation | P50/P95 ms |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |", *rows, "", "## Decision", "", "Strategy selection is manual and must satisfy every safety gate; this report does not calculate a synthetic overall winner.", ""])


def main() -> int:
    report = run_holdout(repository_root=ROOT, dataset_path=DATASET, settings=get_settings())
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MARKDOWN.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"dataset": report["dataset_version"], "case_count": report["case_count"], "statuses": {key: value["status"] for key, value in report["strategies"].items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
