from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.agent.evaluation_regression.baseline import EvaluationBaselineError, load_baseline
from server.agent.evaluation_regression.registry import (
    EvaluationRegistry,
    RegisteredEvaluationSuite,
    _retrieval_failure,
)
from server.agent.evaluation_regression.reporter import report_to_markdown, write_report
from server.agent.evaluation_regression.runner import UnifiedEvaluationRunner
from server.agent.evaluation_regression.schemas import (
    EvaluationCaseResult,
    EvaluationFailureCategory,
    EvaluationRunStatus,
    EvaluationSuiteResult,
)


def suite_result(
    *,
    suite: str = "coach",
    metrics: list[dict[str, object]] | None = None,
    status: EvaluationRunStatus = EvaluationRunStatus.PASS,
) -> EvaluationSuiteResult:
    return EvaluationSuiteResult(
        suite=suite,
        version="fictional-v1",
        started_at=datetime.now(timezone.utc),
        duration_ms=1.0,
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        skipped_cases=0,
        metrics=metrics or [
            {"name": "case_pass_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "forbidden_tool_call_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "rule_violation_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "unsupported_claim_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "warning_retention_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "intent_accuracy", "category": "TOOL", "current": 1.0},
            {"name": "required_tool_recall", "category": "TOOL", "current": 1.0},
            {"name": "decision_consistency", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "fallback_success_rate", "category": "RELIABILITY", "current": 1.0},
        ],
        provider_mode="offline",
        dataset_type="public_fictional",
        status=status,
        cases=[EvaluationCaseResult(case_id="fictional_001", category="fictional", passed=True)],
    )


def write_baseline(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "baseline_version": "test-baseline-v1",
                "product_version": "0.13.0",
                "created_at": "2026-08-10T00:00:00Z",
                "suites": {
                    "coach": {
                        "version": "fictional-v1",
                        "dataset_version": "fictional-v1",
                        "metrics": {
                            "case_pass_rate": 1.0,
                            "forbidden_tool_call_rate": 0.0,
                            "rule_violation_rate": 0.0,
                            "unsupported_claim_rate": 0.0,
                            "warning_retention_rate": 1.0,
                            "intent_accuracy": 1.0,
                            "required_tool_recall": 1.0,
                            "decision_consistency": 1.0,
                            "fallback_success_rate": 1.0,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def fake_registry(result: EvaluationSuiteResult) -> EvaluationRegistry:
    registry = EvaluationRegistry()
    registry._suites = {"coach": RegisteredEvaluationSuite("coach", lambda: result)}
    return registry


def test_registry_lists_only_public_suites() -> None:
    registry = EvaluationRegistry()
    assert registry.suite_names == ("coach", "rag", "retrieval", "weekly_adaptive")
    assert "competition" not in registry.suite_names
    with pytest.raises(KeyError, match="Unknown public evaluation suite"):
        registry.get("private")


def test_unknown_suite_is_rejected_before_execution(tmp_path: Path) -> None:
    runner = UnifiedEvaluationRunner(
        registry=fake_registry(suite_result()), baseline_path=write_baseline(tmp_path / "baseline.json")
    )
    with pytest.raises(KeyError, match="Unknown public evaluation suite"):
        runner.run(["missing"])


def test_single_suite_adds_baseline_and_safety_gates(tmp_path: Path) -> None:
    runner = UnifiedEvaluationRunner(
        registry=fake_registry(suite_result()), baseline_path=write_baseline(tmp_path / "baseline.json")
    )
    run = runner.run(["coach"])
    assert run.status == EvaluationRunStatus.PASS
    assert run.suites[0].metrics[0].baseline == 1.0
    assert all(gate.passed for gate in run.suites[0].gates)


def test_safety_regression_fails_without_mutating_baseline(tmp_path: Path) -> None:
    baseline_path = write_baseline(tmp_path / "baseline.json")
    before = baseline_path.read_bytes()
    result = suite_result(
        metrics=[
            {"name": "forbidden_tool_call_rate", "category": "AGENT_SAFETY", "current": 0.1},
            {"name": "rule_violation_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "unsupported_claim_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "warning_retention_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "case_pass_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "intent_accuracy", "category": "TOOL", "current": 1.0},
            {"name": "required_tool_recall", "category": "TOOL", "current": 1.0},
            {"name": "decision_consistency", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "fallback_success_rate", "category": "RELIABILITY", "current": 1.0},
        ]
    )
    run = UnifiedEvaluationRunner(
        registry=fake_registry(result), baseline_path=baseline_path
    ).run(["coach"])
    assert run.status == EvaluationRunStatus.FAIL
    assert baseline_path.read_bytes() == before


def test_improvement_is_not_a_regression(tmp_path: Path) -> None:
    baseline_path = write_baseline(tmp_path / "baseline.json")
    result = suite_result(
        metrics=[
            {"name": "case_pass_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "forbidden_tool_call_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "rule_violation_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "unsupported_claim_rate", "category": "AGENT_SAFETY", "current": 0.0},
            {"name": "warning_retention_rate", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "intent_accuracy", "category": "TOOL", "current": 1.0},
            {"name": "required_tool_recall", "category": "TOOL", "current": 1.0},
            {"name": "decision_consistency", "category": "AGENT_SAFETY", "current": 1.0},
            {"name": "fallback_success_rate", "category": "RELIABILITY", "current": 1.0},
        ]
    )
    run = UnifiedEvaluationRunner(
        registry=fake_registry(result), baseline_path=baseline_path
    ).run(["coach"])
    assert run.status == EvaluationRunStatus.PASS


def test_environment_blocker_and_provider_failure_are_separate(tmp_path: Path) -> None:
    baseline_path = write_baseline(tmp_path / "baseline.json")
    registry = EvaluationRegistry()
    registry._suites = {
        "coach": RegisteredEvaluationSuite("coach", lambda: (_ for _ in ()).throw(RuntimeError("private")))
    }
    run = UnifiedEvaluationRunner(registry=registry, baseline_path=baseline_path).run(["coach"])
    assert run.status == EvaluationRunStatus.BLOCKED
    assert run.suites[0].cases[0].failure_category == EvaluationFailureCategory.ENVIRONMENT_BLOCKER
    assert _retrieval_failure(
        SimpleNamespace(passed=False, failure_codes=["PROVIDER_FAILURE"])
    ) == EvaluationFailureCategory.PROVIDER_FAILURE


def test_baseline_missing_and_invalid_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(EvaluationBaselineError):
        load_baseline(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(EvaluationBaselineError):
        load_baseline(bad)


def test_json_and_markdown_reports_are_safe_and_public_only(tmp_path: Path) -> None:
    run = UnifiedEvaluationRunner(
        registry=fake_registry(suite_result()), baseline_path=write_baseline(tmp_path / "baseline.json")
    ).run(["coach"])
    json_path, markdown_path = write_report(run, output_dir=tmp_path / "runs")
    serialized = json_path.read_text(encoding="utf-8") + markdown_path.read_text(encoding="utf-8")
    assert "prompt" not in serialized.lower()
    assert "reasoning_content" not in serialized
    assert "competition" not in serialized.lower()
    assert "fictional_001" in serialized


def test_public_coach_run_is_deterministic_except_runtime_metadata() -> None:
    first = EvaluationRegistry().get("coach").run()
    second = EvaluationRegistry().get("coach").run()
    assert [item.model_dump(exclude={"duration_ms", "started_at"}) for item in first.cases] == [
        item.model_dump(exclude={"duration_ms", "started_at"}) for item in second.cases
    ]


def test_public_registry_runs_all_existing_suites() -> None:
    run = UnifiedEvaluationRunner().run()
    assert [item.suite for item in run.suites] == [
        "coach",
        "rag",
        "retrieval",
        "weekly_adaptive",
    ]
    assert sum(item.total_cases for item in run.suites) == 160
    assert run.status == EvaluationRunStatus.PARTIAL
    assert not any(
        not gate.passed and gate.safety_critical
        for suite in run.suites
        for gate in suite.gates
    )
