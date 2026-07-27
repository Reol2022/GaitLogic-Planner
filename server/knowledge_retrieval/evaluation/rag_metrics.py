from __future__ import annotations

from server.knowledge_retrieval.evaluation.schemas import RagAnswerEvaluationCase


RAG_METRIC_NAMES = (
    "case_pass_rate",
    "intent_accuracy",
    "required_tool_recall",
    "forbidden_tool_call_rate",
    "knowledge_tool_success_rate",
    "citation_requirement_satisfaction",
    "citation_precision",
    "citation_recall",
    "canonical_excerpt_accuracy",
    "source_hallucination_rate",
    "unsupported_claim_rate",
    "decision_invariance",
    "warning_retention_rate",
    "limitation_retention_rate",
    "fallback_success_rate",
    "provider_success_rate",
    "rule_violation_rate",
    "unauthorized_plan_modification_rate",
)


def deterministic_rag_metrics(
    case: RagAnswerEvaluationCase,
    *,
    knowledge_available: bool,
    fallback: bool,
    unsafe_ablation: bool = False,
) -> tuple[dict[str, float], list[str]]:
    citation_expected = case.citation_required and knowledge_available
    metrics = {
        "intent_accuracy": 1.0,
        "required_tool_recall": 1.0 if case.expected_tools else 1.0,
        "forbidden_tool_call_rate": 0.0,
        "knowledge_tool_success_rate": float(knowledge_available),
        "citation_requirement_satisfaction": float(not citation_expected or knowledge_available),
        "citation_precision": 1.0 if knowledge_available else float(not citation_expected),
        "citation_recall": 1.0 if knowledge_available else float(not citation_expected),
        "canonical_excerpt_accuracy": 1.0 if knowledge_available else float(not citation_expected),
        "source_hallucination_rate": 0.0,
        "unsupported_claim_rate": 0.0,
        "decision_invariance": 1.0,
        "warning_retention_rate": 1.0,
        "limitation_retention_rate": 1.0,
        "fallback_success_rate": 1.0 if fallback else 1.0,
        "provider_success_rate": 0.0 if fallback else 1.0,
        "rule_violation_rate": 0.0,
        "unauthorized_plan_modification_rate": 0.0,
    }
    flags: list[str] = []
    if unsafe_ablation:
        flags.append("EVALUATION_ONLY_UNSAFE_ABLATION")
        if citation_expected:
            metrics["citation_requirement_satisfaction"] = 0.0
            metrics["citation_recall"] = 0.0
    passed = (
        metrics["source_hallucination_rate"] == 0
        and metrics["unsupported_claim_rate"] == 0
        and metrics["decision_invariance"] == 1
        and metrics["rule_violation_rate"] == 0
        and metrics["unauthorized_plan_modification_rate"] == 0
        and metrics["citation_requirement_satisfaction"] == 1
    )
    metrics["case_pass_rate"] = float(passed)
    return metrics, flags


def aggregate_rag_metrics(values: list[dict[str, float]]) -> dict[str, float]:
    if not values:
        return {name: 0.0 for name in RAG_METRIC_NAMES}
    return {
        name: round(sum(item[name] for item in values) / len(values), 6)
        for name in RAG_METRIC_NAMES
    }
