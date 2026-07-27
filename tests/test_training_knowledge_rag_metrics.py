from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.evaluation.datasets import load_rag_dataset
from server.knowledge_retrieval.evaluation.rag_metrics import (
    aggregate_rag_metrics,
    deterministic_rag_metrics,
)


def test_full_system_preserves_citations_and_decision() -> None:
    case = load_rag_dataset(
        Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json")
    ).cases[0]
    metrics, flags = deterministic_rag_metrics(
        case, knowledge_available=True, fallback=False
    )
    assert metrics["citation_requirement_satisfaction"] == 1.0
    assert metrics["decision_invariance"] == 1.0
    assert metrics["unsupported_claim_rate"] == 0.0
    assert flags == []


def test_unsafe_ablation_is_labelled_and_does_not_fake_citation_success() -> None:
    case = load_rag_dataset(
        Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json")
    ).cases[0]
    metrics, flags = deterministic_rag_metrics(
        case,
        knowledge_available=True,
        fallback=False,
        unsafe_ablation=True,
    )
    assert metrics["citation_requirement_satisfaction"] == 0.0
    assert flags == ["EVALUATION_ONLY_UNSAFE_ABLATION"]


def test_rag_metric_empty_aggregation_is_defined() -> None:
    metrics = aggregate_rag_metrics([])
    assert metrics["case_pass_rate"] == 0.0
    assert metrics["rule_violation_rate"] == 0.0
