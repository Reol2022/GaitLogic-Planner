from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from planner_core.training_knowledge.condition_evaluator import read_field
from planner_core.training_knowledge.enums import RuleEvaluationStatus
from planner_core.training_knowledge.operators import MISSING
from planner_core.training_knowledge.schemas import EngineEvaluationResult, TrainingRuleDefinition


ALLOWED_LIFECYCLE_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"approved", "rejected"},
    "approved": {"published", "draft"},
    "published": {"deprecated"},
    "deprecated": {"published", "retired"},
    "rejected": {"draft"},
    "retired": set(),
}

BUSINESS_THRESHOLD_OPERATORS = {"gt", "gte", "lt", "lte", "between"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def rule_content_payload(rule: TrainingRuleDefinition | dict[str, Any]) -> dict[str, Any]:
    if isinstance(rule, TrainingRuleDefinition):
        return {
            "code": rule.code,
            "version": rule.version,
            "name": rule.name,
            "description": rule.description,
            "category": rule.category,
            "scope": rule.scope,
            "conditions": rule.conditions,
            "result": rule.result.model_dump(mode="json"),
            "applicability": rule.applicability.model_dump(mode="json"),
            "thresholds": [item.model_dump(mode="json") for item in rule.thresholds],
            "explanation_template": rule.explanation_template,
            "severity": rule.severity.value,
            "priority": rule.priority,
            "source_type": rule.source_type.value,
        }
    keys = [
        "rule_code",
        "version",
        "name",
        "description",
        "category",
        "scope",
        "conditions_json",
        "result_json",
        "applicability_json",
        "thresholds_json",
        "explanation_template",
        "severity",
        "priority",
        "source_type",
    ]
    return {key: rule.get(key) for key in keys if key in rule}


def validate_lifecycle_transition(current: str, target: str) -> None:
    if target not in ALLOWED_LIFECYCLE_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid lifecycle transition: {current} -> {target}.")


def applicability_status(rule: TrainingRuleDefinition, facts: dict[str, Any]) -> tuple[RuleEvaluationStatus, str | None, list[str]]:
    applicability = rule.applicability
    sport = read_field(facts, "athlete.sport")
    if sport is not MISSING and applicability.sports and sport not in applicability.sports:
        return RuleEvaluationStatus.not_applicable, "sport_not_supported", []
    missing = []
    for path in applicability.requires_fields:
        if read_field(facts, path) is MISSING:
            missing.append(path)
    if missing:
        return RuleEvaluationStatus.insufficient_data, "required_fields_missing", missing
    return RuleEvaluationStatus.not_matched, None, []


def collect_numeric_threshold_conditions(condition: Any) -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if not isinstance(condition, dict):
        return result
    if "all" in condition:
        for item in condition["all"]:
            result.extend(collect_numeric_threshold_conditions(item))
        return result
    if "any" in condition:
        for item in condition["any"]:
            result.extend(collect_numeric_threshold_conditions(item))
        return result
    if "not" in condition:
        return collect_numeric_threshold_conditions(condition["not"])
    operator = condition.get("operator")
    value = condition.get("value")
    if operator in BUSINESS_THRESHOLD_OPERATORS and isinstance(value, (int, float, dict)):
        result.append((str(condition.get("field")), value))
    return result


def validate_threshold_declarations(rule: TrainingRuleDefinition) -> list[str]:
    errors: list[str] = []
    declared = {item.key for item in rule.thresholds}
    numeric_conditions = collect_numeric_threshold_conditions(rule.conditions)
    if numeric_conditions and not declared:
        errors.append(f"Rule {rule.code} uses numeric threshold conditions without threshold declarations.")
    for threshold in rule.thresholds:
        if not threshold.unit:
            errors.append(f"Threshold {threshold.key} is missing unit.")
        if not threshold.description:
            errors.append(f"Threshold {threshold.key} is missing description.")
    return errors


def diff_results(expected: dict[str, Any], actual: EngineEvaluationResult) -> dict[str, Any]:
    actual_codes = [item.rule_code for item in actual.matched_rules]
    failures: dict[str, Any] = {}
    expected_codes = expected.get("expected_rule_codes")
    if expected_codes is not None:
        missing = sorted(set(expected_codes) - set(actual_codes))
        if missing:
            failures["missing_rule_codes"] = missing
    unexpected = expected.get("unexpected_rule_codes") or []
    unexpected_hit = sorted(set(unexpected) & set(actual_codes))
    if unexpected_hit:
        failures["unexpected_rule_codes"] = unexpected_hit
    if expected.get("expected_final_action") and expected["expected_final_action"] != actual.final_action:
        failures["final_action"] = {"expected": expected["expected_final_action"], "actual": actual.final_action}
    if expected.get("expected_dominant_rule_code") and expected["expected_dominant_rule_code"] != actual.dominant_rule_code:
        failures["dominant_rule_code"] = {
            "expected": expected["expected_dominant_rule_code"],
            "actual": actual.dominant_rule_code,
        }
    expected_status = expected.get("expected_status")
    if expected_status == "matched" and not actual_codes:
        failures["status"] = {"expected": "matched", "actual": "not_matched"}
    if expected_status == "not_matched" and actual_codes:
        failures["status"] = {"expected": "not_matched", "actual": "matched"}
    return failures


def safe_package_member(path: str) -> bool:
    if not path or path.startswith("/") or path.startswith("\\"):
        return False
    if ".." in re.split(r"[\\/]+", path):
        return False
    return True
