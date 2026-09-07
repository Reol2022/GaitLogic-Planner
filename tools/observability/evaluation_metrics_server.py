#!/usr/bin/env python3
"""Serve read-only Prometheus metrics from a checked-in evaluation CSV.

This process is intentionally independent from the GaitLogic request path.  It
never reads application databases or runtime user data.
"""

from __future__ import annotations

import argparse
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


METRICS = {
    "fact_consistency": "gaitlogic_eval_fact_consistency",
    "partial_facts_response": "gaitlogic_eval_partial_facts_rate",
    "false_global_block": "gaitlogic_eval_false_global_block_rate",
    "blocked_domain_hallucination": "gaitlogic_eval_blocked_domain_hallucination_rate",
    "average_latency_ms": "gaitlogic_eval_latency_milliseconds",
    "average_total_tokens": "gaitlogic_eval_total_tokens",
}


def render_metrics(artifact: Path) -> str:
    """Render only stable aggregate fields actually present in the artifact."""

    artifact = Path(artifact)
    with artifact.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    lines = ["# HELP gaitlogic_eval_artifact_loaded Evaluation artifact availability.", "# TYPE gaitlogic_eval_artifact_loaded gauge", "gaitlogic_eval_artifact_loaded 1"]
    for field, name in METRICS.items():
        available = [row for row in rows if row.get("variant") and row.get(field) not in (None, "")]
        if not available:
            continue
        lines.extend((f"# HELP {name} Read-only aggregate from the fixed evaluation artifact.", f"# TYPE {name} gauge"))
        for row in available:
            try:
                value = float(row[field])
            except ValueError:
                continue
            lines.append(f'{name}{{variant="{row["variant"]}"}} {value}')
    return "\n".join(lines) + "\n"


def make_handler(artifact: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path not in {"/metrics", "/healthz"}:
                self.send_error(404)
                return
            if self.path == "/healthz":
                payload = b"ok\n"
            else:
                try:
                    payload = render_metrics(artifact).encode()
                except (OSError, csv.Error):
                    self.send_error(503)
                    return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9464)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), make_handler(args.artifact)).serve_forever()


if __name__ == "__main__":
    main()
