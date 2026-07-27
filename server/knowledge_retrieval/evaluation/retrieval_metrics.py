from __future__ import annotations

import math

from server.knowledge_retrieval.evaluation.schemas import (
    RankedItem,
    RetrievalEvaluationCase,
)


def _dcg(relevances: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(relevances, 1))


def evaluate_retrieval_case(
    case: RetrievalEvaluationCase,
    ranked: list[RankedItem],
) -> tuple[dict[str, float], list[str]]:
    relevant = {item.document_id: item.relevance for item in case.relevant_documents}
    documents: list[str] = []
    for item in ranked:
        if item.document_id not in documents:
            documents.append(item.document_id)
        if len(documents) == 4:
            break
    metrics: dict[str, float] = {}
    failures: list[str] = []
    if case.should_abstain:
        abstained = not ranked
        metrics.update(
            {
                "abstention_precision": float(abstained),
                "abstention_recall": float(abstained),
                "empty_result_accuracy": float(abstained),
            }
        )
        if not abstained:
            failures.append("EXPECTED_ABSTENTION")
    else:
        unique_relevant = set(relevant)
        for k in (1, 3, 4):
            top = documents[:k]
            hits = len(unique_relevant & set(top))
            metrics[f"hit_at_{k}"] = float(hits > 0)
            metrics[f"recall_at_{k}"] = (
                round(hits / len(unique_relevant), 6) if unique_relevant else 1.0
            )
        reciprocal = 0.0
        for rank, document_id in enumerate(documents, 1):
            if document_id in relevant:
                reciprocal = 1.0 / rank
                break
        metrics["mrr_at_4"] = round(reciprocal, 6)
        actual_grades = [relevant.get(document_id, 0) for document_id in documents]
        ideal_grades = sorted(relevant.values(), reverse=True)[:4]
        ideal = _dcg(ideal_grades)
        metrics["ndcg_at_4"] = round(_dcg(actual_grades) / ideal, 6) if ideal else 1.0
        metrics["empty_result_accuracy"] = float(bool(ranked))
        if metrics["recall_at_4"] < 1:
            failures.append("RELEVANT_DOCUMENT_MISSED")
    forbidden = bool(set(documents) & set(case.forbidden_document_ids))
    filter_violation = False
    metrics["forbidden_document_rate"] = float(forbidden)
    metrics["filter_violation_rate"] = float(filter_violation)
    if forbidden:
        failures.append("FORBIDDEN_DOCUMENT_RETRIEVED")
    return metrics, failures


def aggregate_retrieval_metrics(
    cases: list[tuple[RetrievalEvaluationCase, dict[str, float]]],
) -> dict[str, float]:
    names = sorted({name for _, values in cases for name in values})
    result: dict[str, float] = {}
    for name in names:
        eligible = [
            values[name]
            for case, values in cases
            if name in values
            and not (
                case.should_abstain
                and name.startswith(("hit_at_", "recall_at_", "mrr_", "ndcg_"))
            )
        ]
        result[name] = round(sum(eligible) / len(eligible), 6) if eligible else 0.0
    return result
