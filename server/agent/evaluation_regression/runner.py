from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from server.agent.evaluation_regression.baseline import load_baseline
from server.agent.evaluation_regression.gates import evaluate_gates
from server.agent.evaluation_regression.registry import EvaluationRegistry, REPOSITORY_ROOT
from server.agent.evaluation_regression.schemas import (
    EvaluationFailureCategory,
    EvaluationMetric,
    EvaluationRun,
    EvaluationRunStatus,
    EvaluationSuiteResult,
)


DEFAULT_BASELINE = Path("docs/evaluation/baselines/agent-regression-v1.json")


class UnifiedEvaluationRunner:
    """Runs existing public suites without changing their cases or metrics."""

    def __init__(
        self,
        *,
        registry: EvaluationRegistry | None = None,
        baseline_path: Path = DEFAULT_BASELINE,
    ) -> None:
        self.registry = registry or EvaluationRegistry()
        self.baseline_path = baseline_path

    def run(self, suites: list[str] | None = None) -> EvaluationRun:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        baseline_location = (
            self.baseline_path
            if self.baseline_path.is_absolute()
            else REPOSITORY_ROOT / self.baseline_path
        )
        baseline = load_baseline(baseline_location.resolve())
        selected = suites or list(self.registry.suite_names)
        results: list[EvaluationSuiteResult] = []
        for suite_name in selected:
            suite = self.registry.get(suite_name)
            try:
                result = suite.run()
            except Exception:
                result = EvaluationSuiteResult(
                    suite=suite_name,
                    version="unavailable",
                    started_at=datetime.now(timezone.utc),
                    duration_ms=0.0,
                    total_cases=0,
                    passed_cases=0,
                    failed_cases=0,
                    skipped_cases=0,
                    provider_mode="offline",
                    dataset_type="public_fictional",
                    status=EvaluationRunStatus.BLOCKED,
                    cases=[
                        {
                            "case_id": f"{suite_name}_environment",
                            "category": "environment",
                            "passed": False,
                            "failure_category": EvaluationFailureCategory.ENVIRONMENT_BLOCKER,
                            "safe_error_codes": ["EVALUATION_SUITE_UNAVAILABLE"],
                        }
                    ],
                    limitations=["The public suite could not run in this environment."],
                )
            baseline_suite = baseline.suites.get(suite_name)
            current_metrics = {item.name: item.current for item in result.metrics}
            result.metrics = [
                EvaluationMetric(
                    name=item.name,
                    category=item.category,
                    current=item.current,
                    baseline=(baseline_suite.metrics.get(item.name) if baseline_suite else None),
                    delta=(
                        item.current - baseline_suite.metrics[item.name]
                        if baseline_suite and item.name in baseline_suite.metrics
                        else None
                    ),
                )
                for item in result.metrics
            ]
            result.gates = evaluate_gates(
                suite=suite_name,
                metrics=current_metrics,
                baseline=baseline_suite,
            )
            if result.status != EvaluationRunStatus.BLOCKED and any(
                not gate.passed for gate in result.gates
            ):
                result.status = EvaluationRunStatus.FAIL
            results.append(result)
        status = self._run_status(results)
        return EvaluationRun(
            run_id=str(uuid4()),
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            provider_mode="offline",
            baseline_version=baseline.baseline_version,
            status=status,
            suites=results,
        )

    @staticmethod
    def _run_status(results: list[EvaluationSuiteResult]) -> EvaluationRunStatus:
        if any(result.status == EvaluationRunStatus.BLOCKED for result in results):
            return EvaluationRunStatus.BLOCKED
        if any(
            result.status == EvaluationRunStatus.FAIL
            and any(not gate.passed and gate.safety_critical for gate in result.gates)
            for result in results
        ):
            return EvaluationRunStatus.FAIL
        if any(result.status in {EvaluationRunStatus.FAIL, EvaluationRunStatus.PARTIAL} for result in results):
            return EvaluationRunStatus.PARTIAL
        return EvaluationRunStatus.PASS
