from __future__ import annotations

from typing import Any

from planner_core.training_knowledge.operators import MISSING, OperatorTypeError, evaluate_operator
from planner_core.training_knowledge.enums import RuleEvaluationStatus
from planner_core.training_knowledge.schemas import ConditionEvaluation, FIELD_PATH_PATTERN

MAX_CONDITION_DEPTH = 12
MAX_CONDITION_COUNT = 100


def read_field(facts: dict[str, Any], path: str) -> Any:
    if not FIELD_PATH_PATTERN.match(path):
        raise ValueError("Unsafe field path.")
    current: Any = facts
    for segment in path.split("."):
        if segment.startswith("_"):
            raise ValueError("Unsafe field path.")
        if not isinstance(current, dict) or segment not in current:
            return MISSING
        current = current[segment]
    return current


def count_conditions(condition: dict[str, Any]) -> int:
    if not isinstance(condition, dict):
        return 1
    if "all" in condition:
        return sum(count_conditions(item) for item in condition["all"])
    if "any" in condition:
        return sum(count_conditions(item) for item in condition["any"])
    if "not" in condition:
        return count_conditions(condition["not"])
    return 1


class ConditionEvaluator:
    def __init__(self, max_depth: int = MAX_CONDITION_DEPTH, max_conditions: int = MAX_CONDITION_COUNT) -> None:
        self.max_depth = max_depth
        self.max_conditions = max_conditions

    def evaluate(self, condition: dict[str, Any], facts: dict[str, Any]) -> ConditionEvaluation:
        if count_conditions(condition) > self.max_conditions:
            return ConditionEvaluation(matched=False, errors=["Condition count exceeds limit."], status=RuleEvaluationStatus.error)
        return self._evaluate(condition, facts, depth=1)

    def _evaluate(self, condition: Any, facts: dict[str, Any], depth: int) -> ConditionEvaluation:
        if depth > self.max_depth:
            return ConditionEvaluation(matched=False, errors=["Condition depth exceeds limit."], status=RuleEvaluationStatus.error)
        if not isinstance(condition, dict):
            return ConditionEvaluation(matched=False, errors=["Condition must be an object."], status=RuleEvaluationStatus.error)
        if "all" in condition:
            items = condition.get("all")
            if not isinstance(items, list) or not items:
                return ConditionEvaluation(matched=False, errors=["all must be a non-empty array."], status=RuleEvaluationStatus.error)
            results = [self._evaluate(item, facts, depth + 1) for item in items]
            return self._combine(all(result.matched for result in results), results)
        if "any" in condition:
            items = condition.get("any")
            if not isinstance(items, list) or not items:
                return ConditionEvaluation(matched=False, errors=["any must be a non-empty array."], status=RuleEvaluationStatus.error)
            results = [self._evaluate(item, facts, depth + 1) for item in items]
            return self._combine(any(result.matched for result in results), results)
        if "not" in condition:
            result = self._evaluate(condition["not"], facts, depth + 1)
            return ConditionEvaluation(
                matched=not result.matched if not result.errors else False,
                missing_fields=result.missing_fields,
                errors=result.errors,
                status=RuleEvaluationStatus.matched if not result.matched and not result.errors else result.status,
            )
        return self._evaluate_leaf(condition, facts)

    def _evaluate_leaf(self, condition: dict[str, Any], facts: dict[str, Any]) -> ConditionEvaluation:
        field = condition.get("field")
        operator = condition.get("operator")
        if not isinstance(field, str) or not isinstance(operator, str):
            return ConditionEvaluation(matched=False, errors=["Leaf condition requires field and operator."], status=RuleEvaluationStatus.error)
        try:
            actual = read_field(facts, field)
            matched = evaluate_operator(operator, actual, condition.get("value"))
        except (ValueError, OperatorTypeError) as exc:
            return ConditionEvaluation(matched=False, errors=[str(exc)], status=RuleEvaluationStatus.error)
        missing = [field] if actual is MISSING else []
        status = RuleEvaluationStatus.insufficient_data if missing else RuleEvaluationStatus.matched if matched else RuleEvaluationStatus.not_matched
        return ConditionEvaluation(matched=matched, missing_fields=missing, status=status)

    @staticmethod
    def _combine(matched: bool, results: list[ConditionEvaluation]) -> ConditionEvaluation:
        missing: list[str] = []
        errors: list[str] = []
        for result in results:
            missing.extend(result.missing_fields)
            errors.extend(result.errors)
        return ConditionEvaluation(
            matched=matched and not errors,
            missing_fields=sorted(set(missing)),
            errors=errors,
            status=(
                RuleEvaluationStatus.error
                if errors
                else RuleEvaluationStatus.insufficient_data
                if missing and not matched
                else RuleEvaluationStatus.matched
                if matched
                else RuleEvaluationStatus.not_matched
            ),
        )
