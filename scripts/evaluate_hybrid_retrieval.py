"""Evaluate Dense, BM25, and equal-weight RRF on the public retrieval set."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider  # noqa: E402
from server.knowledge_retrieval.evaluation.bm25_comparison import run_bm25_comparison  # noqa: E402
from server.knowledge_retrieval.evaluation.datasets import load_retrieval_dataset  # noqa: E402
from server.knowledge_retrieval.evaluation.retrieval_metrics import aggregate_retrieval_metrics, evaluate_retrieval_case  # noqa: E402
from server.knowledge_retrieval.evaluation.runner import TrainingKnowledgeEvaluationRunner  # noqa: E402
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode, RankedItem  # noqa: E402
from server.knowledge_retrieval.hybrid.retriever import HybridKnowledgeRetriever  # noqa: E402
from server.knowledge_retrieval.index_service import KnowledgeIndexService  # noqa: E402
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest  # noqa: E402
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever  # noqa: E402
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService  # noqa: E402
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever  # noqa: E402

DATASET = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"
REPORT_DIR = ROOT / "docs/evaluation/reports"


def _count_cases(cases, field: str) -> list[str]:
    return [item["case_id"] for item in cases if item[field]]


def _oracle(case, dense, bm25, depth: int) -> float:
    relevant = {item.document_id for item in case.relevant_documents}
    if case.should_abstain:
        return 1.0
    request = KnowledgeRetrievalRequest(query=case.query, top_k=min(depth, 10), categories=case.filters.categories, tags=case.filters.tags, language=case.language)
    # Candidate depth is an internal evaluation parameter; public request
    # validation remains capped at ten. Backends accept the safe bounded model
    # copy for the 12-candidate Oracle diagnostic only.
    candidate_request = request.model_copy(update={"top_k": depth})
    candidates = {item.document_id for item in dense.retrieve(candidate_request).results}
    candidates |= {item.document_id for item in bm25.retrieve(candidate_request).results}
    return len(relevant & candidates) / len(relevant) if relevant else 1.0


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="gaitlogic-hybrid-eval-") as raw:
        root = Path(raw)
        (root / "knowledge/manifests").mkdir(parents=True)
        shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", root / "knowledge/manifests/corpus-v1.json")
        dense_service = KnowledgeIndexService(repository_root=root, index_root=Path("var/dense"))
        dense_index = dense_service.build(DeterministicEmbeddingProvider(dimensions=64, environment="test"))
        dense_report = TrainingKnowledgeEvaluationRunner(repository_root=root, index_root=Path("var/dense")).run_retrieval(dataset_path=DATASET, provider_factory=lambda: DeterministicEmbeddingProvider(dimensions=64, environment="test"), provider_name="deterministic_test", model_name="deterministic-sha256-v1", mode=EvaluationMode.DENSE_WITH_METADATA, index_id=dense_index.manifest.index_id)
        bm25_comparison = run_bm25_comparison(repository_root=root, dataset_path=DATASET, dense_report=dense_report)
        bm25_service = Bm25IndexService(repository_root=root)
        bm25_index = bm25_service.build()
        dataset = load_retrieval_dataset(DATASET, corpus_manifest_path=root / "knowledge/manifests/corpus-v1.json")
        dense = TrainingKnowledgeRetriever(index_service=dense_service, provider=DeterministicEmbeddingProvider(dimensions=64, environment="test"), index_id=dense_index.manifest.index_id)
        bm25 = TrainingKnowledgeBm25Retriever(index_service=bm25_service, index_id=bm25_index.index_id)
        hybrid = HybridKnowledgeRetriever(dense_retriever=dense, bm25_retriever=bm25, dense_candidate_depth=8, bm25_candidate_depth=8)
        cases, aggregate = [], []
        for case in dataset.cases:
            response = hybrid.retrieve(KnowledgeRetrievalRequest(query=case.query, top_k=4, categories=case.filters.categories, tags=case.filters.tags, language=case.language))
            ranked = [RankedItem(rank=item.rank, chunk_id=item.chunk_id, document_id=item.document_id, score=item.score) for item in response.results]
            metrics, failures = evaluate_retrieval_case(case, ranked)
            aggregate.append((case, metrics))
            cases.append({"case_id": case.case_id, "passed": not failures, "failure_codes": failures, "ranked_items": [item.model_dump() for item in ranked]})
        dense_cases = {item.case_id: item for item in dense_report.cases}
        bm25_cases = {item["case_id"]: item for item in bm25_comparison["bm25_case_results"]}
        hybrid_ok = {item["case_id"]: item["passed"] for item in cases}
        case_by_id = {case.case_id: case for case in dataset.cases}
        def has_forbidden(case_id, items):
            forbidden = set(case_by_id[case_id].forbidden_document_ids)
            return bool(forbidden & {item["document_id"] if isinstance(item, dict) else item.document_id for item in items})
        dense_forbidden = {case_id for case_id, item in dense_cases.items() if has_forbidden(case_id, [value.model_dump() for value in item.ranked_items])}
        bm25_forbidden = {case_id for case_id, item in bm25_cases.items() if has_forbidden(case_id, item["ranked_items"])}
        hybrid_forbidden = {item["case_id"] for item in cases if has_forbidden(item["case_id"], item["ranked_items"])}
        oracle = {str(depth): round(sum(_oracle(case, dense, bm25, depth) for case in dataset.cases) / len(dataset.cases), 6) for depth in (4, 8, 12)}
        return {
            "comparison_version": "retrieval-hybrid-comparison-1.0.0", "dataset_version": dataset.dataset_version, "top_k": 4,
            "candidate_depth": {"dense": 8, "bm25": 8},
            "dense": {"case_count": dense_report.case_count, "metrics": dense_report.metrics, "failure_case_ids": dense_report.failure_case_ids},
            "bm25": bm25_comparison["bm25"],
            "hybrid_rrf": {"case_count": len(cases), "metrics": aggregate_retrieval_metrics(aggregate), "failure_case_ids": [item["case_id"] for item in cases if not item["passed"]]},
            "comparison": {
                "hybrid_recovered_vs_dense": [case_id for case_id, item in hybrid_ok.items() if item and not dense_cases[case_id].passed],
                "hybrid_regressed_vs_dense": [case_id for case_id, item in hybrid_ok.items() if not item and dense_cases[case_id].passed],
                "hybrid_recovered_vs_bm25": [case_id for case_id, item in hybrid_ok.items() if item and not bm25_cases[case_id]["passed"]],
                "hybrid_regressed_vs_bm25": [case_id for case_id, item in hybrid_ok.items() if not item and bm25_cases[case_id]["passed"]],
                "all_fail": [case_id for case_id, item in hybrid_ok.items() if not item and not dense_cases[case_id].passed and not bm25_cases[case_id]["passed"]],
            },
            "oracle_candidate_recall": oracle,
            "forbidden_analysis": {
                "dense_cases": sorted(dense_forbidden), "bm25_cases": sorted(bm25_forbidden), "hybrid_cases": sorted(hybrid_forbidden),
                "promoted_by_fusion": sorted(hybrid_forbidden - dense_forbidden - bm25_forbidden),
                "suppressed_from_dense": sorted(dense_forbidden - hybrid_forbidden),
                "suppressed_from_bm25": sorted(bm25_forbidden - hybrid_forbidden),
            },
            "hybrid_cases": cases,
            "safety": {"raw_query_saved": False, "chunk_text_saved": False, "private_cases_used": False},
        }


def _markdown(report: dict[str, object]) -> str:
    def row(name, data):
        m=data["metrics"]; return f"| {name} | {data['case_count']} | {m.get('recall_at_4', 0):.4f} | {m.get('mrr_at_4', 0):.4f} | {m.get('ndcg_at_4', 0):.4f} | {m.get('forbidden_document_rate', 0):.4f} | {m.get('filter_violation_rate', 0):.4f} |"
    c=report["comparison"]
    return f"""# Dense、BM25 与 Hybrid RRF 对比 v1

同一公开 60-case 数据集、相同 Corpus、metadata filter 和最终 `top_k=4`。Hybrid 使用固定等权 `RRF(k=60)`，Dense/BM25 候选深度均固定为 8；4/8/12 仅用于 Oracle candidate coverage 诊断，未用于调参。

| Strategy | Pass cases | Recall@4 | MRR@4 | nDCG@4 | Forbidden rate | Filter violation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{row('Dense', report['dense'])}
{row('BM25', report['bm25'])}
{row('Hybrid RRF', report['hybrid_rrf'])}

## Change sets

- Hybrid recovered vs Dense: {len(c['hybrid_recovered_vs_dense'])}
- Hybrid regressed vs Dense: {len(c['hybrid_regressed_vs_dense'])}
- Hybrid recovered vs BM25: {len(c['hybrid_recovered_vs_bm25'])}
- Hybrid regressed vs BM25: {len(c['hybrid_regressed_vs_bm25'])}
- All fail: {len(c['all_fail'])}

## Oracle candidate recall

`{report['oracle_candidate_recall']}`

Oracle is evaluation-only: it asks whether a relevant document appeared in the union candidate set. It is not a production score or rank. If candidate recall is high while top-4 remains poor, reranking may be justified; if candidate recall is low, improve retrieval/corpus coverage first.
"""


def main() -> int:
    report = run()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "retrieval-hybrid-comparison-v1.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (REPORT_DIR / "retrieval-hybrid-comparison-v1.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"hybrid_pass": report["hybrid_rrf"]["case_count"] - len(report["hybrid_rrf"]["failure_case_ids"]), "comparison": {key: len(value) for key,value in report["comparison"].items()}, "oracle": report["oracle_candidate_recall"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
