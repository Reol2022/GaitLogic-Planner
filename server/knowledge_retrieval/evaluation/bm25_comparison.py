"""Public dense-vs-BM25 retrieval comparison without changing either baseline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from server.knowledge_retrieval.evaluation.datasets import load_retrieval_dataset
from server.knowledge_retrieval.evaluation.retrieval_metrics import aggregate_retrieval_metrics, evaluate_retrieval_case
from server.knowledge_retrieval.evaluation.schemas import RankedItem
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever


@dataclass(frozen=True)
class RetrievalComparisonCase:
    case_id: str
    dense_passed: bool
    bm25_passed: bool
    dense_rank: int | None
    bm25_rank: int | None
    expected_documents: list[str]
    failure_category: str


def _first_relevant_rank(case, ranked: list[RankedItem]) -> int | None:
    relevant = {item.document_id for item in case.relevant_documents}
    return next((item.rank for item in ranked if item.document_id in relevant), None)


def _category(case, dense_passed: bool, bm25_passed: bool) -> str:
    """Conservative, reproducible review labels; no gold labels are changed."""
    query = case.query.lower()
    if case.should_abstain:
        return "hard_negative_or_abstention"
    if dense_passed != bm25_passed:
        if any(token in query for token in ("rpe", "vdot", "5k", "10k", "hrv")):
            return "abbreviation_or_exact_terminology"
        return "lexical_semantic_complement"
    if not dense_passed:
        if case.filters.categories or case.filters.tags:
            return "metadata_filter_or_coverage"
        return "semantic_confusion_or_ambiguous_relevance"
    return "both_success"


def run_bm25_comparison(*, repository_root: Path, dataset_path: Path, dense_report) -> dict[str, object]:
    """Evaluate a BM25 index with the exact same public data and top-k as Dense."""
    root = repository_root.resolve()
    dataset = load_retrieval_dataset(dataset_path, corpus_manifest_path=root / "knowledge/manifests/corpus-v1.json")
    service = Bm25IndexService(repository_root=root)
    manifest = service.build()
    retriever = TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id)
    dense_cases = {item.case_id: item for item in dense_report.cases}
    bm25_results: list[dict[str, object]] = []
    aggregate_input: list[tuple[object, dict[str, float]]] = []
    comparison: list[RetrievalComparisonCase] = []
    for case in dataset.cases:
        started = perf_counter()
        response = retriever.retrieve(KnowledgeRetrievalRequest(query=case.query, top_k=4, categories=case.filters.categories, tags=case.filters.tags, language=case.language))
        ranked = [RankedItem(rank=item.rank, chunk_id=item.chunk_id, document_id=item.document_id, score=item.score) for item in response.results]
        metrics, failures = evaluate_retrieval_case(case, ranked)
        aggregate_input.append((case, metrics))
        passed = not failures
        bm25_results.append({"case_id": case.case_id, "passed": passed, "ranked_items": [item.model_dump() for item in ranked], "metrics": metrics, "failure_codes": failures, "duration_ms": round((perf_counter() - started) * 1000, 3)})
        dense = dense_cases[case.case_id]
        dense_passed = bool(dense.passed)
        comparison.append(RetrievalComparisonCase(case_id=case.case_id, dense_passed=dense_passed, bm25_passed=passed, dense_rank=_first_relevant_rank(case, dense.ranked_items), bm25_rank=_first_relevant_rank(case, ranked), expected_documents=[item.document_id for item in case.relevant_documents], failure_category=_category(case, dense_passed, passed)))
    bm25_metrics = aggregate_retrieval_metrics(aggregate_input)  # type: ignore[arg-type]
    return {
        "comparison_version": "retrieval-bm25-comparison-1.0.0",
        "dataset_version": dataset.dataset_version,
        "dataset_sha256": dataset.content_sha256,
        "corpus_root_hash": manifest.corpus_root_hash,
        "top_k": 4,
        "dense": {"case_count": dense_report.case_count, "metrics": dense_report.metrics, "failure_case_ids": dense_report.failure_case_ids},
        "bm25": {"index_id": manifest.index_id, "case_count": len(bm25_results), "metrics": bm25_metrics, "failure_case_ids": [item["case_id"] for item in bm25_results if not item["passed"]]},
        "overlap": {
            "dense_only_success": [item.case_id for item in comparison if item.dense_passed and not item.bm25_passed],
            "bm25_only_success": [item.case_id for item in comparison if item.bm25_passed and not item.dense_passed],
            "both_success": [item.case_id for item in comparison if item.dense_passed and item.bm25_passed],
            "both_fail": [item.case_id for item in comparison if not item.dense_passed and not item.bm25_passed],
        },
        "cases": [asdict(item) for item in comparison],
        "bm25_case_results": bm25_results,
        "safety": {"raw_query_saved": False, "chunk_text_saved": False, "embeddings_saved": False, "private_cases_used": False},
    }
