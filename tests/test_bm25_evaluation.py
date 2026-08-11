from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.evaluation.bm25_comparison import run_bm25_comparison
from server.knowledge_retrieval.evaluation.runner import TrainingKnowledgeEvaluationRunner
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode
from server.knowledge_retrieval.index_service import KnowledgeIndexService


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"


def test_bm25_comparison_keeps_dense_baseline_independent() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "knowledge/manifests").mkdir(parents=True)
        shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", root / "knowledge/manifests/corpus-v1.json")
        service = KnowledgeIndexService(repository_root=root, index_root=Path("var/dense"))
        index = service.build(DeterministicEmbeddingProvider(dimensions=64, environment="test"))
        dense = TrainingKnowledgeEvaluationRunner(repository_root=root, index_root=Path("var/dense")).run_retrieval(
            dataset_path=DATASET, provider_factory=lambda: DeterministicEmbeddingProvider(dimensions=64, environment="test"),
            provider_name="deterministic_test", model_name="deterministic-sha256-v1", mode=EvaluationMode.DENSE_WITH_METADATA, index_id=index.manifest.index_id,
        )
        report = run_bm25_comparison(repository_root=root, dataset_path=DATASET, dense_report=dense)
    assert dense.case_count == 60
    assert len(dense.failure_case_ids) == 17
    assert report["bm25"]["case_count"] == 60
    assert sum(len(value) for value in report["overlap"].values()) == 60
    assert report["safety"]["private_cases_used"] is False
