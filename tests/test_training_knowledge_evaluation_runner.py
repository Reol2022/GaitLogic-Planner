from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.evaluation.runner import (
    TrainingKnowledgeEvaluationRunner,
)
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode


ROOT = Path.cwd()


def test_retrieval_runner_is_deterministic_except_runtime_metadata() -> None:
    runner = TrainingKnowledgeEvaluationRunner(repository_root=ROOT)
    factory = lambda: DeterministicEmbeddingProvider(
        dimensions=64, environment="test"
    )
    first = runner.run_retrieval(
        dataset_path=ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json",
        provider_factory=factory,
        provider_name="deterministic_test",
        model_name="deterministic-sha256-v1",
        mode=EvaluationMode.DENSE_WITH_METADATA,
    )
    second = runner.run_retrieval(
        dataset_path=ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json",
        provider_factory=factory,
        provider_name="deterministic_test",
        model_name="deterministic-sha256-v1",
        mode=EvaluationMode.DENSE_WITH_METADATA,
    )
    assert first.result_hash == second.result_hash
    assert first.metrics == second.metrics
    assert not first.raw_answers_saved


def test_rag_runner_stores_only_safe_summary_fields() -> None:
    report = TrainingKnowledgeEvaluationRunner(repository_root=ROOT).run_rag(
        dataset_path=ROOT / "docs/rag/evaluation/cases/rag-answer-eval-v1.json"
    )
    payload = report.model_dump_json()
    assert report.case_count == 36
    assert report.metrics["decision_invariance"] == 1.0
    assert '"raw_answer"' not in payload
    assert '"prompt"' not in payload
    assert '"reasoning_content"' not in payload
    assert '"vector"' not in payload
    assert '"api_key"' not in payload
