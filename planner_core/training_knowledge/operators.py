from __future__ import annotations

from numbers import Real
from typing import Any


class MissingValue:
    pass


MISSING = MissingValue()


class OperatorTypeError(ValueError):
    pass


def _number_pair(left: Any, right: Any) -> tuple[Real, Real]:
    if isinstance(left, bool) or isinstance(right, bool):
        raise OperatorTypeError("Boolean values are not numeric operands.")
    if not isinstance(left, Real) or not isinstance(right, Real):
        raise OperatorTypeError("Numeric comparison requires int or float operands.")
    return left, right


def evaluate_operator(operator: str, actual: Any, expected: Any) -> bool:
    if operator == "exists":
        return actual is not MISSING
    if actual is MISSING:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator in {"gt", "gte", "lt", "lte"}:
        left, right = _number_pair(actual, expected)
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        return left <= right
    if operator == "in":
        if not isinstance(expected, list):
            raise OperatorTypeError("in requires an array value.")
        return actual in expected
    if operator == "not_in":
        if not isinstance(expected, list):
            raise OperatorTypeError("not_in requires an array value.")
        return actual not in expected
    if operator == "between":
        if not isinstance(expected, dict):
            raise OperatorTypeError("between requires an object value.")
        minimum, maximum = _number_pair(expected.get("min"), expected.get("max"))
        value, _ = _number_pair(actual, minimum)
        include_min = expected.get("include_min", True)
        include_max = expected.get("include_max", True)
        lower = value >= minimum if include_min else value > minimum
        upper = value <= maximum if include_max else value < maximum
        return lower and upper
    raise ValueError(f"Unsupported operator: {operator}")

