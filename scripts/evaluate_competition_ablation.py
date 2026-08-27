from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.agent.competition_ablation.loader import load_ablation_cases
from server.agent.competition_ablation.provider import (
    DeterministicAblationProvider,
    RealAblationProvider,
)
from server.agent.competition_ablation.reporter import report_to_markdown, write_report
from server.agent.competition_ablation.runner import CompetitionAblationRunner
from server.agent.competition_ablation.schemas import AblationVariant
from server.agent.competition_ablation.schemas import CompetitionAblationReport


DEFAULT_CASES = Path("evaluation/competition_ablation/cases_v1.jsonl")
DEFAULT_OUTPUT = Path("docs/evaluation/competition-ablation-v1/results")


def _relative_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("path must be repository-relative")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the public-fictional, production-isolated competition ablation."
    )
    parser.add_argument("--phase", choices=("pilot", "full", "safety"), default="pilot")
    parser.add_argument("--provider-mode", choices=("offline", "real"), default="offline")
    parser.add_argument("--cases", type=_relative_path, default=DEFAULT_CASES)
    parser.add_argument("--output-dir", type=_relative_path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runs", type=int)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--variant", action="append", choices=tuple(item.value for item in AblationVariant), default=[])
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse successful runs from the existing report for the selected phase.",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser


def _pilot_allows_full(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    runs = data.get("runs")
    if data.get("phase") != "pilot" or data.get("provider_mode") != "real" or not runs:
        return False
    succeeded = sum(item.get("status") == "SUCCEEDED" for item in runs)
    return succeeded / len(runs) >= 0.95


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.runs is not None and not 1 <= args.runs <= 3:
        print("ERROR: --runs must be between 1 and 3", file=sys.stderr)
        return 2
    output_directory = (ROOT / args.output_dir).resolve()
    if args.phase in {"full", "safety"} and args.provider_mode == "real":
        if not _pilot_allows_full(output_directory / "pilot.json"):
            print(
                "ERROR: a real-provider pilot with at least 95% schema/provider success is required",
                file=sys.stderr,
            )
            return 3
    cases = load_ablation_cases((ROOT / args.cases).resolve())
    provider = (
        RealAblationProvider()
        if args.provider_mode == "real"
        else DeterministicAblationProvider()
    )
    runs_per_case = args.runs or (1 if args.phase == "pilot" else 3)
    existing_runs = None
    if args.resume:
        existing_path = output_directory / f"{args.phase}.json"
        if existing_path.is_file():
            try:
                existing = CompetitionAblationReport.model_validate_json(
                    existing_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                print("ERROR: existing report cannot be resumed safely", file=sys.stderr)
                return 4
            expected = (
                args.phase,
                "offline" if provider.provider_alias == "deterministic_offline" else "real",
                provider.provider_alias,
                provider.model_alias,
                provider.thinking_mode,
                runs_per_case,
            )
            actual = (
                existing.phase,
                existing.provider_mode,
                existing.provider_alias,
                existing.model_alias,
                existing.thinking_mode,
                existing.runs_per_case,
            )
            if actual != expected:
                print(
                    "ERROR: existing report configuration does not match this run",
                    file=sys.stderr,
                )
                return 4
            existing_runs = existing.runs
    runner = CompetitionAblationRunner(provider)
    try:
        report = runner.run(
            cases=cases,
            phase=args.phase,
            runs_per_case=runs_per_case,
            fail_fast=args.fail_fast,
            case_ids=set(args.case_id) if args.case_id else None,
            variants_override=(
                tuple(AblationVariant(item) for item in args.variant)
                if args.variant
                else None
            ),
            existing_runs=existing_runs,
        )
    finally:
        runner.close()
    if args.no_write:
        print(report_to_markdown(report))
    else:
        json_path, csv_path, markdown_path = write_report(
            report,
            output_directory=output_directory,
        )
        print(f"JSON report: {json_path.relative_to(ROOT)}")
        print(f"CSV report: {csv_path.relative_to(ROOT)}")
        print(f"Markdown report: {markdown_path.relative_to(ROOT)}")
    failed = sum(item.status != "SUCCEEDED" for item in report.runs)
    print(
        f"Phase={report.phase} cases={report.case_count} calls={report.total_model_calls} "
        f"provider_or_schema_failures={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
