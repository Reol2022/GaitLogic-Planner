from __future__ import annotations

import csv
import json
from pathlib import Path

from server.agent.competition_ablation.schemas import CompetitionAblationReport


_PRIMARY_METRICS = (
    "fact_consistency",
    "supported_decision",
    "partial_facts_response",
    "false_global_block",
    "blocked_domain_hallucination",
)


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def report_to_markdown(report: CompetitionAblationReport) -> str:
    lines = [
        f"# Competition Ablation {report.phase.title()} Results",
        "",
        f"- Cases: {report.case_count}",
        f"- Runs per case: {report.runs_per_case}",
        f"- Total model calls: {report.total_model_calls}",
        f"- Provider mode: {report.provider_mode}",
        f"- Provider: {report.provider_alias}",
        f"- Model: {report.model_alias}",
        f"- Thinking: {report.thinking_mode}",
        f"- Temperature: {report.temperature}",
        f"- Max output tokens: {report.max_output_tokens}",
        "",
        "| Variant | Fact Consistency | Supported Decision | Partial Facts Response | False Global Block | Blocked Hallucination | Avg Latency (ms) | Avg Tokens |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.summaries:
        metrics = summary.metric_means
        lines.append(
            "| "
            + " | ".join(
                [
                    summary.variant.value,
                    _percent(metrics["fact_consistency"]),
                    _percent(metrics["supported_decision"]),
                    _percent(metrics["partial_facts_response"]),
                    _percent(metrics["false_global_block"]),
                    _percent(metrics["blocked_domain_hallucination"]),
                    f"{summary.average_latency_ms:.2f}",
                    f"{summary.average_total_tokens:.2f}",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Fractions", ""])
    for summary in report.summaries:
        lines.append(f"### {summary.variant.value}")
        lines.append("")
        for name in _PRIMARY_METRICS:
            fraction = summary.metric_fractions[name]
            lines.append(
                f"- {name}: {fraction.numerator}/{fraction.denominator} = {_percent(fraction.value)}"
            )
        lines.append("")
    failures = [item for item in report.runs if item.status != "SUCCEEDED"]
    lines.extend(["## Provider and Schema Failures", ""])
    if not failures:
        lines.append("None.")
    else:
        for item in failures:
            lines.append(
                f"- {item.case_id} / {item.variant.value} / run {item.run_index}: "
                f"{item.status} ({', '.join(item.safe_error_codes) or 'NO_SAFE_CODE'})"
            )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: CompetitionAblationReport,
    *,
    output_directory: Path,
) -> tuple[Path, Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    stem = report.phase
    json_path = output_directory / f"{stem}.json"
    csv_path = output_directory / f"{stem}.csv"
    markdown_path = output_directory.parent / f"{stem}-results.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(report_to_markdown(report), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                *_PRIMARY_METRICS,
                "average_latency_ms",
                "average_total_tokens",
                "success_count",
                "failure_count",
            ]
        )
        for summary in report.summaries:
            writer.writerow(
                [
                    summary.variant.value,
                    *[summary.metric_means[name] for name in _PRIMARY_METRICS],
                    summary.average_latency_ms,
                    summary.average_total_tokens,
                    summary.success_count,
                    summary.failure_count,
                ]
            )
    return json_path, csv_path, markdown_path
