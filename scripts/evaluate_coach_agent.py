#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.agent.evaluation.loader import EvaluationCaseLoadError, load_evaluation_cases
from server.agent.evaluation.reporter import report_to_markdown, write_report
from server.agent.evaluation.runner import CoachAgentEvaluationRunner

DEFAULT_CASES = Path("evaluation/coach_agent/cases_v1.jsonl")
DEFAULT_JSON = Path("docs/agent/evaluation/results/coach-agent-eval-v1.json")
DEFAULT_MARKDOWN = Path("docs/agent/evaluation/results/coach-agent-eval-v1.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic offline Coach Agent eval.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--case-id")
    parser.add_argument("--category")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_evaluation_cases(args.cases)
    except EvaluationCaseLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]
    if args.category:
        cases = [case for case in cases if case.category.value == args.category]
    if not cases:
        print("ERROR: no evaluation cases matched the filters", file=sys.stderr)
        return 2

    report = CoachAgentEvaluationRunner().run(cases, fail_fast=args.fail_fast)
    if args.no_write:
        print(report_to_markdown(report))
    else:
        write_report(
            report,
            json_path=args.output_json,
            markdown_path=args.output_markdown,
        )
        print(f"JSON report: {args.output_json}")
        print(f"Markdown report: {args.output_markdown}")
    print(
        f"Cases: {report.summary.passed_cases}/{report.summary.total_cases}; "
        f"pass rate: {report.summary.case_pass_rate:.2%}"
    )
    return 0 if report.summary.passed_cases == report.summary.total_cases else 1


if __name__ == "__main__":
    raise SystemExit(main())
