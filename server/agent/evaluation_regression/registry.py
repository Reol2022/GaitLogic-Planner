from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import shutil
import tempfile
from typing import Callable

from server.agent.evaluation.loader import load_evaluation_cases
from server.agent.evaluation.runner import CoachAgentEvaluationRunner
from server.agent.errors import AgentErrorCode
from server.agent.evaluation_regression.schemas import (
    EvaluationCaseResult,
    EvaluationFailureCategory,
    EvaluationRunStatus,
    EvaluationSuiteResult,
)
from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.evaluation.runner import TrainingKnowledgeEvaluationRunner
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.mcp.evaluation import run_mcp_evaluation
from server.weekly_review_evaluation import load_cases as load_weekly_cases
from server.weekly_review_evaluation import run_evaluation


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _status(*, passed: int, total: int) -> EvaluationRunStatus:
    return EvaluationRunStatus.PASS if passed == total else EvaluationRunStatus.PARTIAL


def _coach_failure(case) -> EvaluationFailureCategory | None:
    if case.passed:
        return None
    if case.rule_violation_found:
        return EvaluationFailureCategory.RULE_FAILURE
    if case.forbidden_tool_called or not case.tool_arguments_valid:
        return EvaluationFailureCategory.TOOL_FAILURE
    if AgentErrorCode.AGENT_VALIDATION_FAILED.value in case.safe_error_codes:
        return EvaluationFailureCategory.VALIDATOR_FAILURE
    if any(
        code
        in {
            AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE.value,
            AgentErrorCode.AGENT_PROVIDER_RATE_LIMITED.value,
            AgentErrorCode.AGENT_PROVIDER_DISABLED.value,
            AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED.value,
        }
        for code in case.safe_error_codes
    ):
        return EvaluationFailureCategory.PROVIDER_FAILURE
    if case.status == "UNAVAILABLE":
        return EvaluationFailureCategory.PROVIDER_FAILURE
    return EvaluationFailureCategory.BUSINESS_FAILURE


def _rag_failure(case) -> EvaluationFailureCategory | None:
    if case.passed:
        return None
    if "PROVIDER_FAILURE" in case.safe_error_codes:
        return EvaluationFailureCategory.PROVIDER_FAILURE
    if case.reference_document_ids:
        return EvaluationFailureCategory.RETRIEVAL_FAILURE
    return EvaluationFailureCategory.VALIDATOR_FAILURE


def _retrieval_failure(case) -> EvaluationFailureCategory | None:
    if case.passed:
        return None
    if "PROVIDER_FAILURE" in case.failure_codes:
        return EvaluationFailureCategory.PROVIDER_FAILURE
    return EvaluationFailureCategory.RETRIEVAL_FAILURE


@dataclass(frozen=True)
class RegisteredEvaluationSuite:
    name: str
    run: Callable[[], EvaluationSuiteResult]


class EvaluationRegistry:
    """Registry of public-only offline suites; no private competition assets."""

    def __init__(self, *, repository_root: Path = REPOSITORY_ROOT) -> None:
        self.repository_root = repository_root
        self._suites = {
            "coach": RegisteredEvaluationSuite("coach", self._run_coach),
            "rag": RegisteredEvaluationSuite("rag", self._run_rag),
            "retrieval": RegisteredEvaluationSuite("retrieval", self._run_retrieval),
            "weekly_adaptive": RegisteredEvaluationSuite(
                "weekly_adaptive", self._run_weekly_adaptive
            ),
            "mcp": RegisteredEvaluationSuite("mcp", self._run_mcp),
        }

    @property
    def suite_names(self) -> tuple[str, ...]:
        return tuple(self._suites)

    def get(self, name: str) -> RegisteredEvaluationSuite:
        try:
            return self._suites[name]
        except KeyError as exc:
            raise KeyError(f"Unknown public evaluation suite: {name}") from exc

    def _run_coach(self) -> EvaluationSuiteResult:
        started_at, started = _utc_now(), perf_counter()
        cases = load_evaluation_cases(self.repository_root / "evaluation/coach_agent/cases_v1.jsonl")
        report = CoachAgentEvaluationRunner().run(cases)
        results = [
            EvaluationCaseResult(
                case_id=item.case_id,
                category=item.category.value,
                passed=item.passed,
                failure_category=_coach_failure(item),
                safe_error_codes=item.safe_error_codes,
            )
            for item in report.cases
        ]
        return EvaluationSuiteResult(
            suite="coach",
            version=report.evaluation_version,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            total_cases=report.summary.total_cases,
            passed_cases=report.summary.passed_cases,
            failed_cases=report.summary.total_cases - report.summary.passed_cases,
            skipped_cases=0,
            metrics=[
                {"name": key, "category": "AGENT_SAFETY" if key.endswith(("rate", "consistency")) else "TOOL", "current": value}
                for key, value in report.summary.model_dump().items()
                if isinstance(value, float)
            ],
            provider_mode="offline",
            dataset_type="public_fictional",
            status=_status(passed=report.summary.passed_cases, total=report.summary.total_cases),
            cases=results,
        )

    def _run_rag(self) -> EvaluationSuiteResult:
        started_at, started = _utc_now(), perf_counter()
        report = TrainingKnowledgeEvaluationRunner(repository_root=self.repository_root).run_rag(
            dataset_path=self.repository_root / "docs/rag/evaluation/cases/rag-answer-eval-v1.json",
            mode=EvaluationMode.FULL_SYSTEM,
        )
        results = [
            EvaluationCaseResult(
                case_id=item.case_id,
                category=item.intent.value,
                passed=item.passed,
                failure_category=_rag_failure(item),
                safe_error_codes=item.safe_error_codes,
            )
            for item in report.cases
        ]
        passed = sum(item.passed for item in report.cases)
        return EvaluationSuiteResult(
            suite="rag",
            version=report.evaluation_version,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            total_cases=report.case_count,
            passed_cases=passed,
            failed_cases=report.case_count - passed,
            skipped_cases=0,
            metrics=[
                {"name": key, "category": "RAG", "current": value}
                for key, value in report.metrics.items()
            ],
            provider_mode="offline",
            dataset_type="public_fictional",
            status=_status(passed=passed, total=report.case_count),
            cases=results,
            limitations=report.limitations,
        )

    def _run_retrieval(self) -> EvaluationSuiteResult:
        started_at, started = _utc_now(), perf_counter()
        with tempfile.TemporaryDirectory(prefix="gaitlogic-public-eval-") as directory:
            temporary_root = Path(directory)
            manifest_target = temporary_root / "knowledge/manifests"
            manifest_target.mkdir(parents=True)
            shutil.copyfile(
                self.repository_root / "knowledge/manifests/corpus-v1.json",
                manifest_target / "corpus-v1.json",
            )
            index_service = KnowledgeIndexService(repository_root=temporary_root)
            build = index_service.build(
                DeterministicEmbeddingProvider(dimensions=64, environment="test")
            )
            runner = TrainingKnowledgeEvaluationRunner(repository_root=temporary_root)
            report = runner.run_retrieval(
                dataset_path=self.repository_root / "docs/rag/evaluation/cases/retrieval-eval-v1.json",
                provider_factory=lambda: DeterministicEmbeddingProvider(dimensions=64, environment="test"),
                provider_name="deterministic_test",
                model_name="deterministic-sha256-v1",
                mode=EvaluationMode.DENSE_WITH_METADATA,
                index_id=build.manifest.index_id,
            )
        results = [
            EvaluationCaseResult(
                case_id=item.case_id,
                category="retrieval",
                passed=item.passed,
                failure_category=_retrieval_failure(item),
                safe_error_codes=item.failure_codes,
            )
            for item in report.cases
        ]
        passed = sum(item.passed for item in report.cases)
        return EvaluationSuiteResult(
            suite="retrieval",
            version=report.evaluation_version,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            total_cases=report.case_count,
            passed_cases=passed,
            failed_cases=report.case_count - passed,
            skipped_cases=0,
            metrics=[
                {"name": key, "category": "RETRIEVAL", "current": value}
                for key, value in report.metrics.items()
            ],
            provider_mode="offline",
            dataset_type="public_fictional",
            status=_status(passed=passed, total=report.case_count),
            cases=results,
            limitations=report.limitations,
        )

    def _run_weekly_adaptive(self) -> EvaluationSuiteResult:
        started_at, started = _utc_now(), perf_counter()
        report = run_evaluation(
            load_weekly_cases(self.repository_root / "evaluation/weekly_adaptive/cases_v1.jsonl")
        )
        summary = report["summary"]
        results = [
            EvaluationCaseResult(
                case_id=item["case_id"],
                category=item["category"],
                passed=bool(item["passed"]),
                failure_category=(None if item["passed"] else EvaluationFailureCategory.RULE_FAILURE),
            )
            for item in report["cases"]
        ]
        return EvaluationSuiteResult(
            suite="weekly_adaptive",
            version=report["evaluation_version"],
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            total_cases=summary["total_cases"],
            passed_cases=summary["passed_cases"],
            failed_cases=summary["total_cases"] - summary["passed_cases"],
            skipped_cases=0,
            metrics=[
                {"name": key, "category": "WEEKLY_ADAPTIVE", "current": value}
                for key, value in summary.items()
                if isinstance(value, float)
            ],
            provider_mode="offline",
            dataset_type="public_fictional",
            status=_status(passed=summary["passed_cases"], total=summary["total_cases"]),
            cases=results,
            limitations=report["limitations"],
        )

    def _run_mcp(self) -> EvaluationSuiteResult:
        return run_mcp_evaluation(self.repository_root)
