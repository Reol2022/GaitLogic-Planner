"""Frozen public holdout evaluation and retrieval-strategy ablation.

The module evaluates existing retrievers only.  It never adjusts an index,
corpus, query, label, or retrieval configuration from evaluation outcomes.
Reports intentionally omit query text, chunk text, vectors and provider bodies.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from planner_core.config import Settings
from server.knowledge_retrieval.embeddings.openai_compatible import OpenAICompatibleEmbeddingProvider
from server.knowledge_retrieval.evaluation.datasets import load_retrieval_dataset
from server.knowledge_retrieval.evaluation.retrieval_metrics import aggregate_retrieval_metrics, evaluate_retrieval_case
from server.knowledge_retrieval.evaluation.schemas import RankedItem
from server.knowledge_retrieval.hybrid.retriever import HybridKnowledgeRetriever
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.reranking.retriever import RerankingKnowledgeRetriever
from server.knowledge_retrieval.reranking.siliconflow import SiliconFlowReranker
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever


class Retriever(Protocol):
    def retrieve(self, request: KnowledgeRetrievalRequest): ...


class _MemoizingEvaluationEmbeddingProvider:
    """Process-local cache: repeated ablation queries pay for one embedding.

    The cache is deliberately not persisted and is cleared at completion.  It
    reduces external calls without changing query content, retrieval ranking or
    the frozen evaluation configuration.
    """

    def __init__(self, delegate: OpenAICompatibleEmbeddingProvider) -> None:
        self._delegate = delegate
        self._queries: dict[str, object] = {}
        self.provider_name = delegate.provider_name
        self.model_name = delegate.model_name
        self.dimensions = delegate.dimensions
        self.normalized = delegate.normalized
        self.max_batch_size = delegate.max_batch_size

    def embed_documents(self, texts: list[str]):
        return self._delegate.embed_documents(texts)

    def embed_query(self, text: str):
        value = self._queries.get(text)
        if value is None:
            value = self._delegate.embed_query(text)
            self._queries[text] = value
        return value

    def close(self) -> None:
        # Individual retrievers own only a logical view of the shared client.
        return None

    def close_delegate(self) -> None:
        self._queries.clear()
        self._delegate.close()


STRATEGIES = ("dense_exact", "dense_qdrant", "bm25", "hybrid_rrf", "rerank")


@dataclass(frozen=True)
class StrategyResult:
    status: str
    report: dict[str, object]
    outcomes: dict[str, bool]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    offset = round((len(ordered) - 1) * percentile)
    return round(ordered[offset], 3)


def _safe_error(exc: Exception) -> str:
    category = getattr(exc, "category", None)
    return getattr(category, "value", None) or "RETRIEVAL_FAILURE"


def _request(case) -> KnowledgeRetrievalRequest:
    return KnowledgeRetrievalRequest(query=case.query, top_k=4, categories=case.filters.categories, tags=case.filters.tags, language=case.language)


def _evaluate(name: str, retriever: Retriever, dataset, *, reranker: SiliconFlowReranker | None = None) -> StrategyResult:
    aggregate: list[tuple[object, dict[str, float]]] = []
    cases: list[dict[str, object]] = []
    latencies: list[float] = []
    outcomes: dict[str, bool] = {}
    reliability: Counter[str] = Counter()
    for case in dataset.cases:
        started = perf_counter()
        try:
            response = retriever.retrieve(_request(case))
            ranked = [RankedItem(rank=item.rank, chunk_id=item.chunk_id, document_id=item.document_id, score=item.score) for item in response.results]
            metrics, failures = evaluate_retrieval_case(case, ranked)
            if reranker is not None:
                item = reranker.last_reliability
                reliability["success_count"] += int(item.final_status == "SUCCEEDED")
                reliability["retry_count"] += int(item.retried)
                reliability["fallback_count"] += int(item.final_status != "SUCCEEDED")
                reliability["provider_latency_samples"] += 1
        except Exception as exc:
            ranked = []
            metrics, failures = evaluate_retrieval_case(case, ranked)
            failures.append(_safe_error(exc))
            if reranker is not None:
                reliability["failure_count"] += 1
                reliability["fallback_count"] += 1
        duration = round((perf_counter() - started) * 1000, 3)
        latencies.append(duration)
        passed = not failures
        outcomes[case.case_id] = passed
        aggregate.append((case, metrics))
        # Safe result: IDs and metric values only, never user-like query text or excerpts.
        cases.append({"case_id": case.case_id, "passed": passed, "failure_codes": sorted(set(failures)), "ranked_document_ids": [item.document_id for item in ranked], "duration_ms": duration})
    metrics = aggregate_retrieval_metrics(aggregate)  # type: ignore[arg-type]
    metrics.update({"case_pass_rate": round(sum(outcomes.values()) / max(len(outcomes), 1), 6), "p50_latency_ms": _percentile(latencies, .50), "p95_latency_ms": _percentile(latencies, .95)})
    report: dict[str, object] = {"strategy": name, "status": "COMPLETED", "case_count": len(cases), "passed_cases": sum(outcomes.values()), "metrics": metrics, "failure_case_ids": [row["case_id"] for row in cases if not row["passed"]], "cases": cases}
    if reranker is not None:
        report["provider_reliability"] = {"provider_success_rate": round(reliability["success_count"] / max(len(cases), 1), 6), "success_count": reliability["success_count"], "failure_count": reliability["failure_count"], "retry_count": reliability["retry_count"], "fallback_count": reliability["fallback_count"], "average_provider_latency_ms": metrics["p50_latency_ms"]}
    return StrategyResult("COMPLETED", report, outcomes)


def _pairwise(left: StrategyResult, right: StrategyResult) -> dict[str, list[str]]:
    identifiers = sorted(left.outcomes)
    return {"recovered_cases": [item for item in identifiers if right.outcomes[item] and not left.outcomes[item]], "regressed_cases": [item for item in identifiers if left.outcomes[item] and not right.outcomes[item]], "both_pass": [item for item in identifiers if left.outcomes[item] and right.outcomes[item]], "both_fail": [item for item in identifiers if not left.outcomes[item] and not right.outcomes[item]]}


def _forbidden_analysis(results: dict[str, StrategyResult], dataset) -> dict[str, list[dict[str, object]]]:
    labels = {case.case_id: set(case.forbidden_document_ids) for case in dataset.cases if case.forbidden_document_ids}
    answer: dict[str, list[dict[str, object]]] = {}
    for name, result in results.items():
        if result.status != "COMPLETED":
            continue
        rows: list[dict[str, object]] = []
        for row in result.report["cases"]:  # type: ignore[index]
            forbidden = labels.get(row["case_id"], set())
            ranked = row["ranked_document_ids"]
            for rank, document_id in enumerate(ranked, 1):
                if document_id in forbidden:
                    rows.append({"case_id": row["case_id"], "document_id": document_id, "rank": rank, "failure_category": "FORBIDDEN_DOCUMENT_RETRIEVED"})
        answer[name] = rows
    return answer


def run_holdout(*, repository_root: Path, dataset_path: Path, settings: Settings) -> dict[str, object]:
    """Evaluate fixed strategies using existing published index artifacts."""
    dataset = load_retrieval_dataset(dataset_path, corpus_manifest_path=repository_root / "knowledge/manifests/corpus-v1.json")
    if dataset.dataset_version != "retrieval-holdout-v2":
        raise ValueError("holdout runner accepts only retrieval-holdout-v2")
    dense_service = KnowledgeIndexService(repository_root=repository_root, index_root=Path(settings.knowledge_index_runtime_directory), vector_store=settings.knowledge_vector_store, qdrant_url=settings.qdrant_url, qdrant_api_key=settings.qdrant_api_key, qdrant_collection_prefix=settings.qdrant_collection_prefix)
    bm25_service = Bm25IndexService(repository_root=repository_root, index_root=Path(settings.knowledge_bm25_index_runtime_directory))
    results: dict[str, StrategyResult] = {}
    if not settings.knowledge_embedding_enabled or not settings.knowledge_embedding_api_key or not settings.coach_agent_knowledge_index_id:
        for name in ("dense_exact", "dense_qdrant", "hybrid_rrf", "rerank"):
            results[name] = StrategyResult("NOT_EVALUATED_REAL_PROVIDER", {"strategy": name, "status": "NOT_EVALUATED_REAL_PROVIDER"}, {})
    else:
        provider = _MemoizingEvaluationEmbeddingProvider(OpenAICompatibleEmbeddingProvider(settings))
        dense_exact = TrainingKnowledgeRetriever(index_service=dense_service, provider=provider, index_id=settings.coach_agent_knowledge_index_id, vector_store="exact")
        results["dense_exact"] = _evaluate("dense_exact", dense_exact, dataset)
        # A Qdrant result is only meaningful when the Qdrant artifact and endpoint are configured.
        if settings.knowledge_vector_store == "qdrant" and settings.qdrant_url:
            q_provider = _MemoizingEvaluationEmbeddingProvider(OpenAICompatibleEmbeddingProvider(settings))
            qdrant = TrainingKnowledgeRetriever(index_service=dense_service, provider=q_provider, index_id=settings.coach_agent_knowledge_index_id, vector_store="qdrant", qdrant_url=settings.qdrant_url, qdrant_api_key=settings.qdrant_api_key, qdrant_collection_prefix=settings.qdrant_collection_prefix)
            results["dense_qdrant"] = _evaluate("dense_qdrant", qdrant, dataset)
        else:
            results["dense_qdrant"] = StrategyResult("ENVIRONMENT_SKIPPED", {"strategy": "dense_qdrant", "status": "ENVIRONMENT_SKIPPED"}, {})
    if settings.coach_agent_knowledge_bm25_index_id:
        bm25 = TrainingKnowledgeBm25Retriever(index_service=bm25_service, index_id=settings.coach_agent_knowledge_bm25_index_id)
        results["bm25"] = _evaluate("bm25", bm25, dataset)
        if results["dense_exact"].status == "COMPLETED":
            hybrid = HybridKnowledgeRetriever(dense_retriever=dense_exact, bm25_retriever=bm25, dense_candidate_depth=8, bm25_candidate_depth=8)
            results["hybrid_rrf"] = _evaluate("hybrid_rrf", hybrid, dataset)
            if settings.knowledge_reranker_enabled and settings.knowledge_reranker_effective_api_key:
                reranker = SiliconFlowReranker(settings)
                try:
                    rerank = RerankingKnowledgeRetriever(dense_retriever=dense_exact, bm25_retriever=bm25, reranker=reranker, corpus_manifest_path=dense_service.corpus_manifest_path)
                    results["rerank"] = _evaluate("rerank", rerank, dataset, reranker=reranker)
                finally:
                    reranker.close()
            else:
                results["rerank"] = StrategyResult("NOT_EVALUATED_REAL_PROVIDER", {"strategy": "rerank", "status": "NOT_EVALUATED_REAL_PROVIDER"}, {})
    else:
        for name in ("bm25", "hybrid_rrf", "rerank"):
            results.setdefault(name, StrategyResult("NOT_EVALUATED_REAL_PROVIDER", {"strategy": name, "status": "NOT_EVALUATED_REAL_PROVIDER"}, {}))
    if settings.knowledge_embedding_enabled and settings.knowledge_embedding_api_key and settings.coach_agent_knowledge_index_id:
        provider.close_delegate()
    completed = {name: item for name, item in results.items() if item.status == "COMPLETED"}
    comparisons = {f"{left}_vs_{right}": _pairwise(left_result, right_result) for left, left_result in completed.items() for right, right_result in completed.items() if left < right}
    return {"evaluation_version": "retrieval-holdout-ablation-1.0.0", "dataset_version": dataset.dataset_version, "dataset_sha256": dataset.content_sha256, "case_count": len(dataset.cases), "strategies": {name: item.report for name, item in results.items()}, "pairwise_comparisons": comparisons, "forbidden_analysis": _forbidden_analysis(results, dataset), "decision_matrix": {"selection": "MANUAL_REVIEW_REQUIRED", "safety_gates": {"filter_violation_rate": 0, "sensitive_leakage": 0, "canonical_reference_violation": 0, "source_hallucination": 0, "agent_safety_regression": 0}, "criteria": ["holdout_case_pass_rate", "recall_at_4", "mrr_at_4", "ndcg_at_4", "forbidden_document_rate", "filter_violation_rate", "latency", "provider_dependency", "fallback", "operational_complexity"]}, "safety": {"raw_query_saved": False, "chunk_text_saved": False, "provider_response_saved": False, "private_competition_data_used": False, "case_specific_production_logic": False}}
