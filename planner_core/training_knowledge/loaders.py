from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from planner_core.training_knowledge.schemas import TrainingKnowledgeItemDefinition, TrainingRuleDefinition
from planner_core.training_knowledge.validators import (
    DefinitionValidationError,
    validate_knowledge_item_definition,
    validate_rule_definition,
)


class KnowledgeLoadError(ValueError):
    pass


def load_structured_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text)
    except Exception as exc:
        raise KnowledgeLoadError(f"{path}: failed to load file: {exc}") from exc
    raise KnowledgeLoadError(f"{path}: unsupported file type.")


def _records_from_payload(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return payload[key]
    raise KnowledgeLoadError(f"Expected a list or object with {key}.")


def load_knowledge_items(path: Path) -> list[TrainingKnowledgeItemDefinition]:
    payload = load_structured_file(path)
    records = _records_from_payload(payload, "items")
    items: list[TrainingKnowledgeItemDefinition] = []
    for index, record in enumerate(records):
        try:
            items.append(validate_knowledge_item_definition(record))
        except DefinitionValidationError as exc:
            raise KnowledgeLoadError(f"{path}: item[{index}] validation failed: {exc}") from exc
    return items


def load_training_rules(path: Path) -> list[TrainingRuleDefinition]:
    payload = load_structured_file(path)
    records = _records_from_payload(payload, "rules")
    rules: list[TrainingRuleDefinition] = []
    for index, record in enumerate(records):
        try:
            rules.append(validate_rule_definition(record))
        except DefinitionValidationError as exc:
            raise KnowledgeLoadError(f"{path}: rule[{index}] validation failed: {exc}") from exc
    return rules


def load_repository(root: Path) -> tuple[list[TrainingKnowledgeItemDefinition], list[TrainingRuleDefinition]]:
    knowledge_dir = root / "knowledge"
    item_paths = sorted((knowledge_dir / "taxonomy").glob("*.y*ml")) + sorted(
        (knowledge_dir / "taxonomy").glob("*.json")
    )
    rule_paths = sorted((knowledge_dir / "rules").glob("*.y*ml")) + sorted(
        (knowledge_dir / "rules").glob("*.json")
    )
    items: list[TrainingKnowledgeItemDefinition] = []
    rules: list[TrainingRuleDefinition] = []
    for path in item_paths:
        items.extend(load_knowledge_items(path))
    for path in rule_paths:
        rules.extend(load_training_rules(path))
    _ensure_unique("knowledge item", [item.code for item in items])
    _ensure_unique("training rule", [rule.code for rule in rules])
    item_codes = {item.code for item in items}
    for item in items:
        missing = sorted(set(item.related_codes) - item_codes)
        if missing:
            raise KnowledgeLoadError(f"{item.code}: missing related knowledge codes: {missing}")
    source_refs = {item.code for item in items}
    for rule in rules:
        missing_refs = sorted(set(rule.evidence_refs) - source_refs)
        if missing_refs:
            raise KnowledgeLoadError(f"{rule.code}: missing evidence refs: {missing_refs}")
    return items, rules


def _ensure_unique(label: str, codes: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for code in codes:
        if code in seen:
            duplicates.add(code)
        seen.add(code)
    if duplicates:
        raise KnowledgeLoadError(f"Duplicate {label} codes: {sorted(duplicates)}")

