from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from planner_core.training_knowledge.condition_evaluator import count_conditions
from planner_core.training_knowledge.explanation import find_invalid_placeholders
from planner_core.training_knowledge.schemas import (
    ConditionLeaf,
    ConditionNode,
    TrainingKnowledgeItemDefinition,
    TrainingRuleDefinition,
)

MAX_RULE_RESULT_JSON_CHARS = 12000


class DefinitionValidationError(ValueError):
    pass


def validate_condition_schema(condition: Any, depth: int = 1, max_depth: int = 12) -> None:
    if depth > max_depth:
        raise DefinitionValidationError("Condition depth exceeds limit.")
    if not isinstance(condition, dict):
        raise DefinitionValidationError("Condition must be an object.")
    if any(key in condition for key in ("all", "any", "not")):
        try:
            ConditionNode.model_validate(condition)
        except ValidationError as exc:
            raise DefinitionValidationError(str(exc)) from exc
        if "all" in condition:
            children = condition["all"]
        elif "any" in condition:
            children = condition["any"]
        else:
            children = [condition["not"]]
        for child in children:
            validate_condition_schema(child, depth + 1, max_depth)
        return
    try:
        ConditionLeaf.model_validate(condition)
    except ValidationError as exc:
        raise DefinitionValidationError(str(exc)) from exc


def validate_knowledge_item_definition(payload: Any) -> TrainingKnowledgeItemDefinition:
    try:
        return TrainingKnowledgeItemDefinition.model_validate(payload)
    except ValidationError as exc:
        raise DefinitionValidationError(str(exc)) from exc


def validate_rule_definition(payload: Any) -> TrainingRuleDefinition:
    try:
        rule = TrainingRuleDefinition.model_validate(payload)
    except ValidationError as exc:
        raise DefinitionValidationError(str(exc)) from exc
    validate_condition_schema(rule.conditions)
    if count_conditions(rule.conditions) > 100:
        raise DefinitionValidationError("Rule condition count exceeds limit.")
    invalid = find_invalid_placeholders(rule.explanation_template)
    if invalid:
        raise DefinitionValidationError(f"Invalid placeholders: {', '.join(invalid)}")
    result_size = len(rule.result.model_dump_json())
    if result_size > MAX_RULE_RESULT_JSON_CHARS:
        raise DefinitionValidationError("Rule result JSON exceeds limit.")
    return rule

