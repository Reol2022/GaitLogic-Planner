from __future__ import annotations

import json
from pathlib import Path

from server.agent.evaluation_regression.schemas import EvaluationRun


def report_to_markdown(run: EvaluationRun) -> str:
    suite_rows = "\n".join(
        f"| {suite.suite} | {suite.passed_cases}/{suite.total_cases} | {suite.status.value} |"
        for suite in run.suites
    )
    metric_rows = "\n".join(
        (
            f"| {suite.suite} | {gate.metric} | "
            f"{next((metric.baseline for metric in suite.metrics if metric.name == gate.metric), 'N/A')} | "
            f"{gate.actual if gate.actual is not None else 'N/A'} | "
            f"{next((metric.delta for metric in suite.metrics if metric.name == gate.metric), 'N/A')} | "
            f"{'PASS' if gate.passed else 'FAIL'} |"
        )
        for suite in run.suites
        for gate in suite.gates
    )
    failures = [
        f"| {suite.suite} | {case.case_id} | {case.failure_category.value if case.failure_category else 'CASE_FAILURE'} |"
        for suite in run.suites
        for case in suite.cases
        if not case.passed
    ]
    return "\n".join(
        [
            "# GaitLogic Agent Regression Report",
            "",
            "This report contains public fictional case identifiers, aggregate metrics, and safe error codes only.",
            "",
            f"- Run ID: `{run.run_id}`",
            f"- Baseline: `{run.baseline_version}`",
            f"- Provider mode: `{run.provider_mode}`",
            f"- Overall: **{run.status.value}**",
            "",
            "## Suites",
            "",
            "| Suite | Cases | Status |\n|---|---:|---|",
            suite_rows or "| None | 0/0 | BLOCKED |",
            "",
            "## Regression",
            "",
            "| Suite | Metric | Baseline | Current | Delta | Gate |\n|---|---|---:|---:|---:|---|",
            metric_rows or "| None | N/A | N/A | N/A | N/A | BLOCKED |",
            "",
            "## Failures",
            "",
            "| Suite | Case ID | Category |\n|---|---|---|",
            "\n".join(failures) if failures else "| None | None | None |",
            "",
            "## Reproduce",
            "",
            "`python scripts/evaluate_agent.py --suite all`",
            "",
        ]
    )


def write_report(run: EvaluationRun, *, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"agent-regression-{run.run_id}.json"
    markdown_path = output_dir / f"agent-regression-{run.run_id}.md"
    json_path.write_text(
        json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(report_to_markdown(run), encoding="utf-8")
    return json_path, markdown_path
