from __future__ import annotations

from collections import defaultdict

from server.agent.evaluation.schemas import (
    CategorySummary,
    EvaluationCaseResult,
    EvaluationSummary,
)


def _ratio(numerator: int | float, denominator: int | float, *, empty: float = 1.0) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else empty


def calculate_summary(results: list[EvaluationCaseResult]) -> EvaluationSummary:
    total = len(results)
    today = [item for item in results if item.expected_decision is not None]
    warnings = [item for item in results if item.warning_retained is not None]
    limitations = [item for item in results if item.limitation_retained is not None]
    fallbacks = [item for item in results if item.used_fallback]
    return EvaluationSummary(
        total_cases=total,
        passed_cases=sum(item.passed for item in results),
        case_pass_rate=_ratio(sum(item.passed for item in results), total, empty=0.0),
        intent_accuracy=_ratio(
            sum(item.actual_intent == item.intent for item in results),
            total,
            empty=0.0,
        ),
        required_tool_recall=_ratio(
            sum(item.required_tool_hits for item in results),
            sum(item.required_tool_total for item in results),
        ),
        forbidden_tool_call_rate=_ratio(
            sum(item.forbidden_tool_called for item in results),
            total,
            empty=0.0,
        ),
        tool_argument_validity=_ratio(
            sum(item.tool_arguments_valid for item in results),
            total,
            empty=0.0,
        ),
        decision_consistency=_ratio(
            sum(item.actual_decision == item.expected_decision for item in today),
            len(today),
        ),
        planned_status_consistency=_ratio(
            sum(
                item.actual_planned_status == item.expected_planned_status
                for item in today
            ),
            len(today),
        ),
        warning_retention_rate=_ratio(
            sum(item.warning_retained is True for item in warnings),
            len(warnings),
        ),
        limitation_retention_rate=_ratio(
            sum(item.limitation_retained is True for item in limitations),
            len(limitations),
        ),
        fallback_success_rate=_ratio(
            sum(item.passed for item in fallbacks),
            len(fallbacks),
        ),
        unsupported_claim_rate=_ratio(
            sum(item.unsupported_claim_found for item in results),
            total,
            empty=0.0,
        ),
        rule_violation_rate=_ratio(
            sum(item.rule_violation_found for item in results),
            total,
            empty=0.0,
        ),
    )


def calculate_categories(
    results: list[EvaluationCaseResult],
) -> dict[str, CategorySummary]:
    grouped: dict[str, list[EvaluationCaseResult]] = defaultdict(list)
    for result in results:
        grouped[result.category.value].append(result)
    return {
        category: CategorySummary(
            total_cases=len(items),
            passed_cases=sum(item.passed for item in items),
            pass_rate=_ratio(sum(item.passed for item in items), len(items), empty=0.0),
        )
        for category, items in sorted(grouped.items())
    }
