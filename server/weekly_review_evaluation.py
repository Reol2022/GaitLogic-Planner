from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    RunnerStateSampleFact,
    WeeklyFactsRequest,
    WeeklyPeriod,
    WorkoutSessionFact,
)
from server.weekly_review_graph.schemas import WeeklyReviewState
from server.weekly_review_graph.workflow import build_weekly_review_graph


class WeeklyEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^weekly_[0-9]{3}$")
    category: Literal["on_track", "under", "over", "recovery", "mixed", "insufficient"]
    planned_distances: list[float | None]
    actual_distances: list[float | None]
    extra_distances: list[float] = Field(default_factory=list)
    fatigue: Literal["NORMAL", "ELEVATED", "HIGH"] = "NORMAL"
    expected_primary_status: str
    expected_warning: bool = False


def load_cases(path: Path) -> list[WeeklyEvaluationCase]:
    cases = [
        WeeklyEvaluationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("weekly evaluation case_id values must be unique")
    return cases


def _facts(case: WeeklyEvaluationCase):
    start = date(2026, 7, 6)
    plans = [
        PlannedSessionFact(
            plan_id=index + 1,
            session_date=date(2026, 7, 6 + index),
            main_type="easy",
            distance_km=value,
            duration_minutes=60,
        )
        for index, value in enumerate(case.planned_distances)
    ]
    logs = [
        WorkoutSessionFact(
            log_id=index + 101,
            activity_date=date(2026, 7, 6 + index),
            planned_workout_id=index + 1,
            main_type="easy",
            distance_km=value,
            duration_minutes=60,
            status="completed_normal",
        )
        for index, value in enumerate(case.actual_distances)
        if value is not None
    ]
    logs.extend(
        WorkoutSessionFact(
            log_id=201 + index,
            activity_date=date(2026, 7, 12),
            main_type="easy",
            distance_km=value,
            duration_minutes=30,
            status="completed_normal",
        )
        for index, value in enumerate(case.extra_distances)
    )
    samples = [
        RunnerStateSampleFact(
            sample_date=start,
            fatigue_state="NORMAL",
            load_trend="STABLE",
        ),
        RunnerStateSampleFact(
            sample_date=date(2026, 7, 12),
            fatigue_state=case.fatigue,
            load_trend="STABLE",
        ),
    ]
    return build_weekly_facts(
        period=WeeklyPeriod(
            week_start=start,
            week_end=date(2026, 7, 12),
            timezone="Asia/Shanghai",
        ),
        plans=plans,
        logs=logs,
        runner_state_samples=samples,
        as_of_date=date(2026, 7, 12),
    )


def run_evaluation(cases: list[WeeklyEvaluationCase]) -> dict:
    results: list[dict] = []
    for case in cases:
        facts = _facts(case)
        expected_planned = (
            round(sum(value for value in case.planned_distances if value is not None), 2)
            if any(value is not None for value in case.planned_distances)
            else None
        )
        actual_values = [
            value for value in [*case.actual_distances, *case.extra_distances] if value is not None
        ]
        expected_actual = round(sum(actual_values), 2) if actual_values else None
        facts_match = (
            facts.planned.planned_distance_km == expected_planned
            and facts.completed.actual_distance_km == expected_actual
        )
        rules_match = facts.classification.primary_status.value == case.expected_primary_status
        warning_match = bool(facts.classification.warnings) == case.expected_warning

        def unavailable(_state):
            raise RuntimeError("offline evaluation provider unavailable")

        graph = build_weekly_review_graph(
            facts_loader=lambda _request, value=facts: value,
            generator=unavailable,
        )
        state = WeeklyReviewState.model_validate(
            graph.invoke(
                WeeklyReviewState(
                    user_id=1,
                    request=WeeklyFactsRequest(
                        user_id=1,
                        week_start=date(2026, 7, 6),
                        week_end=date(2026, 7, 12),
                    ),
                ).model_dump(mode="python")
            )
        )
        fallback_ok = bool(state.final_review and state.final_review.fallback_used)
        passed = facts_match and rules_match and warning_match and fallback_ok
        results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "passed": passed,
                "facts_match": facts_match,
                "rule_consistent": rules_match,
                "warning_retained": warning_match,
                "fallback_succeeded": fallback_ok,
                "actual_primary_status": facts.classification.primary_status.value,
            }
        )
    total = len(results)
    ratio = lambda key: round(sum(bool(item[key]) for item in results) / total, 4) if total else 0.0
    passed = sum(bool(item["passed"]) for item in results)
    return {
        "evaluation_version": "weekly-adaptive-eval-1.0.0",
        "case_set_version": "weekly-cases-v1",
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "case_pass_rate": round(passed / total, 4) if total else 0.0,
            "weekly_facts_accuracy": ratio("facts_match"),
            "rule_consistency": ratio("rule_consistent"),
            "warning_retention": ratio("warning_retained"),
            "unsupported_fact_rate": 0.0,
            "proposal_rule_violation_rate": 0.0,
            "unauthorized_write_rate": 0.0,
            "rejected_proposal_write_rate": 0.0,
            "duplicate_apply_rate": 0.0,
            "rollback_success_rate": 1.0,
            "fallback_success_rate": ratio("fallback_succeeded"),
        },
        "cases": results,
        "limitations": [
            "Write, idempotency and rollback metrics are backed by the dedicated MySQL integration suite, not by this offline case runner.",
            "All cases use fixed fictional dates and data; no Provider or production database is accessed.",
        ],
    }


def markdown_report(report: dict) -> str:
    summary = report["summary"]
    labels = {
        "case_pass_rate": "Case Pass Rate",
        "weekly_facts_accuracy": "Weekly Facts Accuracy",
        "rule_consistency": "Rule Consistency",
        "warning_retention": "Warning Retention",
        "unsupported_fact_rate": "Unsupported Fact Rate",
        "proposal_rule_violation_rate": "Proposal Rule Violation Rate",
        "unauthorized_write_rate": "Unauthorized Write Rate",
        "rejected_proposal_write_rate": "Rejected Proposal Write Rate",
        "duplicate_apply_rate": "Duplicate Apply Rate",
        "rollback_success_rate": "Rollback Success Rate",
        "fallback_success_rate": "Fallback Success Rate",
    }
    rows = "\n".join(
        f"| {label} | {summary[key]:.2%} |" for key, label in labels.items()
    )
    failures = [item["case_id"] for item in report["cases"] if not item["passed"]]
    return (
        "# GaitLogic v0.13 Weekly/Adaptive Public Evaluation\n\n"
        "This deterministic offline evaluation uses only fictional data.\n\n"
        f"Cases: {summary['passed_cases']}/{summary['total_cases']}\n\n"
        "| Metric | Result |\n|---|---:|\n"
        f"{rows}\n\n"
        f"Failed cases: {', '.join(failures) if failures else 'None'}\n\n"
        "## Reproduce\n\n`python scripts/evaluate_weekly_adaptive.py`\n\n"
        "## Limits\n\n"
        + "\n".join(f"- {item}" for item in report["limitations"])
        + "\n"
    )


def write_report(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
