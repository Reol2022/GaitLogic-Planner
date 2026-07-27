from __future__ import annotations

from server.knowledge_retrieval.evaluation.retrieval_metrics import (
    aggregate_retrieval_metrics,
    evaluate_retrieval_case,
)
from server.knowledge_retrieval.evaluation.schemas import (
    RankedItem,
    RetrievalEvaluationCase,
)


def _case(*, abstain: bool = False) -> RetrievalEvaluationCase:
    return RetrievalEvaluationCase.model_validate(
        {
            "case_id": "ret_metric_001",
            "query": "虚构阈值查询",
            "should_abstain": abstain,
            "relevant_documents": (
                []
                if abstain
                else [
                    {"document_id": "a", "relevance": 3},
                    {"document_id": "b", "relevance": 1},
                ]
            ),
            "forbidden_document_ids": ["x"],
        }
    )


def test_retrieval_metrics_support_multi_relevance_and_ndcg() -> None:
    case = _case()
    ranked = [
        RankedItem(rank=1, chunk_id="a-1", document_id="a", score=0.9),
        RankedItem(rank=2, chunk_id="a-2", document_id="a", score=0.8),
        RankedItem(rank=3, chunk_id="b-1", document_id="b", score=0.7),
    ]
    metrics, failures = evaluate_retrieval_case(case, ranked)
    assert metrics["recall_at_3"] == 1.0
    assert 0 <= metrics["ndcg_at_4"] <= 1
    assert failures == []


def test_forbidden_document_is_a_failure() -> None:
    metrics, failures = evaluate_retrieval_case(
        _case(),
        [RankedItem(rank=1, chunk_id="x-1", document_id="x", score=1.0)],
    )
    assert metrics["forbidden_document_rate"] == 1.0
    assert "FORBIDDEN_DOCUMENT_RETRIEVED" in failures


def test_abstention_metrics_and_empty_aggregation() -> None:
    case = _case(abstain=True)
    metrics, failures = evaluate_retrieval_case(case, [])
    assert metrics["abstention_precision"] == 1.0
    assert failures == []
    assert aggregate_retrieval_metrics([(case, metrics)])["abstention_recall"] == 1.0
