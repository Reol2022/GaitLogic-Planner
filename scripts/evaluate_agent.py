#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.agent.evaluation_regression.reporter import report_to_markdown, write_report
from server.agent.evaluation_regression.runner import UnifiedEvaluationRunner


_SUITE_ALIASES = {
    "all": None,
    "coach": ["coach"],
    "rag": ["rag"],
    "retrieval": ["retrieval"],
    "weekly-adaptive": ["weekly_adaptive"],
    "mcp": ["mcp"],
}


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("output path must be repository-relative")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public offline Agent regression suites.")
    parser.add_argument("--suite", choices=tuple(_SUITE_ALIASES), default="all")
    parser.add_argument("--output-dir", type=_relative_path, default=Path("var/evaluations"))
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--provider-mode",
        choices=("offline", "real"),
        default="offline",
        help="Real provider execution is intentionally not part of the unified public suite.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.provider_mode != "offline":
        print("ERROR: real provider mode requires a dedicated smoke command.", file=sys.stderr)
        return 2
    run = UnifiedEvaluationRunner().run(_SUITE_ALIASES[args.suite])
    if args.no_write:
        print(report_to_markdown(run))
    else:
        json_path, markdown_path = write_report(run, output_dir=(ROOT / args.output_dir))
        print(f"JSON report: {json_path.relative_to(ROOT)}")
        print(f"Markdown report: {markdown_path.relative_to(ROOT)}")
    print(f"Overall: {run.status.value}")
    return 0 if run.status.value in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
