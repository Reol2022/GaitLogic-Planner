"""Run the frozen 60-case Dense, BM25, Hybrid, and external-reranker comparison.

The report is intentionally reduced to case IDs, aggregate metrics, and safe
Provider reliability categories.  Queries, chunks, vectors, credentials, and
Provider bodies never leave process memory.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings  # noqa: E402
from server.knowledge_retrieval.embeddings.base import (  # noqa: E402
    EmbeddingProvider,
)
from server.knowledge_retrieval.embeddings.openai_compatible import (  # noqa: E402
    OpenAICompatibleEmbeddingProvider,
)
from server.knowledge_retrieval.embeddings.schemas import (  # noqa: E402
    EmbeddingBatch,
    EmbeddingVector,
)
from server.knowledge_retrieval.evaluation.datasets import (  # noqa: E402
    load_retrieval_dataset,
)
from server.knowledge_retrieval.evaluation.retrieval_metrics import (  # noqa: E402
    aggregate_retrieval_metrics,
    evaluate_retrieval_case,
)
from server.knowledge_retrieval.evaluation.schemas import RankedItem  # noqa: E402
from server.knowledge_retrieval.hybrid.retriever import HybridKnowledgeRetriever  # noqa: E402
from server.knowledge_retrieval.index_service import KnowledgeIndexService  # noqa: E402
from server.knowledge_retrieval.reranking.retriever import (  # noqa: E402
    RerankingKnowledgeRetriever,
)
from server.knowledge_retrieval.reranking.siliconflow import (  # noqa: E402
    RERANK_INSTRUCTION_VERSION,
    SiliconFlowReranker,
)
from server.knowledge_retrieval.retrieval_schemas import (  # noqa: E402
    KnowledgeRetrievalRequest,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever  # noqa: E402
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService  # noqa: E402
from server.knowledge_retrieval.sparse.retriever import (  # noqa: E402
    TrainingKnowledgeBm25Retriever,
)


REPORT_JSON = ROOT / "docs/evaluation/reports/retrieval-reranker-comparison-v1.json"
REPORT_MD = ROOT / "docs/evaluation/reports/retrieval-reranker-comparison-v1.md"
DATASET = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"


class _Retriever(Protocol):
    def retrieve(self, request: KnowledgeRetrievalRequest): ...


class _MemoizingEvaluationEmbeddingProvider:
    """Run-local query cache that prevents repeated paid evaluation calls.

    The cache exists only during this CLI process.  It is deliberately not
    persisted or reported, so neither raw queries nor vectors leave process
    memory.  It delegates all provider identity and validation properties to
    the configured production-compatible provider.
    """

    def __init__(self, delegate: EmbeddingProvider) -> None:
        self._delegate = delegate
        self._queries: dict[str, EmbeddingVector] = {}
        self.provider_name = delegate.provider_name
        self.model_name = delegate.model_name
        self.dimensions = delegate.dimensions
        self.normalized = delegate.normalized
        self.max_batch_size = delegate.max_batch_size

    def embed_documents(self, texts: list[str]) -> EmbeddingBatch:
        return self._delegate.embed_documents(texts)

    def embed_query(self, text: str) -> EmbeddingVector:
        cached = self._queries.get(text)
        if cached is None:
            cached = self._delegate.embed_query(text)
            self._queries[text] = cached
        return cached

    def close(self) -> None:
        """Keep the shared client available while the comparison is running."""

    def close_delegate(self) -> None:
        self._queries.clear()
        self._delegate.close()


def _write(report: dict[str, object]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Reranker comparison v1",
        "",
        f"Status: `{report['status']}`.",
        "",
        "This report stores no raw query, chunk text, vector, credential, or Provider response.",
    ]
    for name in ("dense", "bm25", "hybrid_rrf", "rerank"):
        item = report.get(name)
        if not isinstance(item, dict):
            continue
        metrics = item.get("metrics", {})
        lines.extend(
            [
                "",
                f"## {name}",
                "",
                f"- Passed cases: {item.get('passed_cases', 0)}/{item.get('case_count', 0)}",
                f"- Recall@4: {metrics.get('recall_at_4', 'N/A')}",
                f"- MRR@4: {metrics.get('mrr_at_4', 'N/A')}",
                f"- nDCG@4: {metrics.get('ndcg_at_4', 'N/A')}",
                f"- Forbidden Document Rate: {metrics.get('forbidden_document_rate', 'N/A')}",
                f"- Filter Violation Rate: {metrics.get('filter_violation_rate', 'N/A')}",
            ]
        )
    reliability = report.get("provider_reliability")
    if isinstance(reliability, dict):
        lines.extend(
            [
                "",
                "## Provider reliability",
                "",
                f"- Success: {reliability.get('success_count', 0)}",
                f"- Failure: {reliability.get('failure_count', 0)}",
                f"- Retried: {reliability.get('retry_count', 0)}",
                f"- Fallback: {reliability.get('fallback_count', 0)}",
            ]
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocked(reason: str) -> int:
    _write(
        {
            "comparison_version": "retrieval-reranker-comparison-1.0.0",
            "benchmark": "legacy-public-60-case",
            "status": "REAL_PROVIDER_BLOCKED",
            "reason": reason,
            "raw_query_saved": False,
            "chunk_text_saved": False,
            "provider_response_saved": False,
        }
    )
    print(json.dumps({"status": "REAL_PROVIDER_BLOCKED"}))
    return 2


def _request(case: Any) -> KnowledgeRetrievalRequest:
    return KnowledgeRetrievalRequest(
        query=case.query,
        top_k=4,
        categories=case.filters.categories,
        tags=case.filters.tags,
        language=case.language,
    )


def _safe_category(exc: Exception) -> str:
    category = getattr(exc, "category", None)
    return getattr(category, "value", None) or "RETRIEVAL_FAILURE"


def _run_strategy(
    name: str,
    retriever: _Retriever,
    dataset,
    *,
    provider_reliability: Counter[str] | None = None,
) -> tuple[dict[str, object], list[bool]]:
    aggregate: list[tuple[object, dict[str, float]]] = []
    case_rows: list[dict[str, object]] = []
    outcomes: list[bool] = []
    for case in dataset.cases:
        started = perf_counter()
        failure_category: str | None = None
        try:
            response = retriever.retrieve(_request(case))
            if provider_reliability is not None:
                reliability = retriever.reranker.last_reliability  # type: ignore[attr-defined]
                provider_reliability["success" if reliability.final_status == "SUCCEEDED" else "failure"] += 1
                provider_reliability["retry"] += int(reliability.retried)
                provider_reliability["fallback"] += int(reliability.final_status != "SUCCEEDED")
                if reliability.failure_category is not None:
                    provider_reliability[reliability.failure_category.value] += 1
            ranked = [
                RankedItem(
                    rank=item.rank,
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    score=item.score,
                )
                for item in response.results
            ]
            metrics, failures = evaluate_retrieval_case(case, ranked)
        except Exception as exc:
            failure_category = _safe_category(exc)
            if provider_reliability is not None:
                provider_reliability["failure"] += 1
                provider_reliability["fallback"] += 1
                provider_reliability[failure_category] += 1
            ranked = []
            metrics, failures = evaluate_retrieval_case(case, ranked)
            failures.append(failure_category)
        aggregate.append((case, metrics))
        passed = not failures
        outcomes.append(passed)
        case_rows.append(
            {
                "case_id": case.case_id,
                "passed": passed,
                "failure_codes": sorted(set(failures)),
                "failure_category": failure_category,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            }
        )
    metrics = aggregate_retrieval_metrics(aggregate)  # type: ignore[arg-type]
    return (
        {
            "strategy": name,
            "case_count": len(case_rows),
            "passed_cases": sum(outcomes),
            "failure_case_ids": [item["case_id"] for item in case_rows if not item["passed"]],
            "metrics": metrics,
            "cases": case_rows,
        },
        outcomes,
    )


def _comparison(rerank: list[bool], baseline: list[bool]) -> dict[str, int]:
    return {
        "recovered": sum(current and not previous for current, previous in zip(rerank, baseline, strict=True)),
        "regressed": sum(not current and previous for current, previous in zip(rerank, baseline, strict=True)),
    }


def main() -> int:
    settings = get_settings()
    if not settings.knowledge_reranker_enabled or not settings.knowledge_reranker_effective_api_key:
        return _blocked("Reranker provider is disabled or incomplete.")
    if not settings.knowledge_embedding_enabled or not settings.knowledge_embedding_api_key:
        return _blocked("Embedding provider is disabled or incomplete.")
    if not settings.coach_agent_knowledge_index_id or not settings.coach_agent_knowledge_bm25_index_id:
        return _blocked("Published dense and BM25 indexes are required.")

    try:
        dataset = load_retrieval_dataset(
            DATASET,
            corpus_manifest_path=ROOT / "knowledge/manifests/corpus-v1.json",
        )
        dense_service = KnowledgeIndexService(
            repository_root=ROOT,
            index_root=Path(settings.knowledge_index_runtime_directory),
            vector_store=settings.knowledge_vector_store,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            qdrant_collection_prefix=settings.qdrant_collection_prefix,
        )
        bm25_service = Bm25IndexService(
            repository_root=ROOT,
            index_root=Path(settings.knowledge_bm25_index_runtime_directory),
        )
        embedding_provider = _MemoizingEvaluationEmbeddingProvider(
            OpenAICompatibleEmbeddingProvider(settings)
        )
        dense = TrainingKnowledgeRetriever(
            index_service=dense_service,
            provider=embedding_provider,
            index_id=settings.coach_agent_knowledge_index_id,
            vector_store=settings.knowledge_vector_store,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            qdrant_collection_prefix=settings.qdrant_collection_prefix,
        )
        bm25 = TrainingKnowledgeBm25Retriever(
            index_service=bm25_service,
            index_id=settings.coach_agent_knowledge_bm25_index_id,
        )
        hybrid = HybridKnowledgeRetriever(
            dense_retriever=dense,
            bm25_retriever=bm25,
            dense_candidate_depth=8,
            bm25_candidate_depth=8,
        )
        reranker = SiliconFlowReranker(settings)
        rerank = RerankingKnowledgeRetriever(
            dense_retriever=dense,
            bm25_retriever=bm25,
            reranker=reranker,
            corpus_manifest_path=dense_service.corpus_manifest_path,
        )
    except Exception as exc:
        return _blocked(f"Evaluation setup is unavailable: {_safe_category(exc)}.")

    try:
        dense_report, dense_outcomes = _run_strategy("dense", dense, dataset)
        bm25_report, bm25_outcomes = _run_strategy("bm25", bm25, dataset)
        hybrid_report, hybrid_outcomes = _run_strategy("hybrid_rrf", hybrid, dataset)
        reranker_counts: Counter[str] = Counter()
        rerank_report, rerank_outcomes = _run_strategy(
            "rerank", rerank, dataset, provider_reliability=reranker_counts
        )
    finally:
        reranker.close()
        embedding_provider.close_delegate()

    # The retriever safely falls back to Hybrid RRF. Reliability counts are
    # sampled after each bounded Provider call without saving Provider payloads.
    provider_failures = reranker_counts["failure"]
    report = {
        "comparison_version": "retrieval-reranker-comparison-1.0.0",
        "benchmark": "legacy-public-60-case",
        "status": "COMPLETED" if provider_failures == 0 else "COMPLETED_WITH_PROVIDER_FAILURES",
        "configuration": {
            "candidate_depth": 8,
            "top_k": 4,
            "reranker_provider": reranker.provider_kind,
            "reranker_model": settings.knowledge_reranker_model,
            "instruction_version": RERANK_INSTRUCTION_VERSION,
        },
        "dense": dense_report,
        "bm25": bm25_report,
        "hybrid_rrf": hybrid_report,
        "rerank": rerank_report,
        "rerank_vs_dense": _comparison(rerank_outcomes, dense_outcomes),
        "rerank_vs_bm25": _comparison(rerank_outcomes, bm25_outcomes),
        "rerank_vs_hybrid": _comparison(rerank_outcomes, hybrid_outcomes),
        "provider_reliability": {
            "success_count": reranker_counts["success"],
            "failure_count": provider_failures,
            "retry_count": reranker_counts["retry"],
            "fallback_count": reranker_counts["fallback"],
            "failure_categories": {
                key: value
                for key, value in sorted(reranker_counts.items())
                if key.startswith("PROVIDER_")
            },
        },
        "raw_query_saved": False,
        "chunk_text_saved": False,
        "provider_response_saved": False,
    }
    _write(report)
    print(json.dumps({"status": report["status"]}))
    return 0 if provider_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
