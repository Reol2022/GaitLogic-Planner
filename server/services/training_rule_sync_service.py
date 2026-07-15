from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner_core.database.models import TrainingKnowledgeItem, TrainingRule
from planner_core.training_knowledge.loaders import load_repository
from planner_core.training_knowledge.schemas import TrainingKnowledgeItemDefinition, TrainingRuleDefinition
from server.common.exceptions import BadRequestError


def _semver_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".", 2)
    patch_number = ""
    for char in patch:
        if char.isdigit():
            patch_number += char
        else:
            break
    return int(major), int(minor), int(patch_number or 0)


def _knowledge_payload(item: TrainingKnowledgeItemDefinition) -> dict[str, Any]:
    return {
        "code": item.code,
        "name": item.name,
        "english_name": item.english_name,
        "category": item.category,
        "definition": item.definition,
        "aliases_json": item.aliases,
        "attributes_json": item.attributes,
        "related_codes_json": item.related_codes,
        "source_refs_json": item.source_refs,
        "evidence_level": item.evidence_level.value,
        "version": item.version,
        "status": item.status.value,
    }


def _rule_payload(rule: TrainingRuleDefinition) -> dict[str, Any]:
    return {
        "code": rule.code,
        "name": rule.name,
        "description": rule.description,
        "category": rule.category,
        "scope": rule.scope,
        "conditions_json": rule.conditions,
        "result_json": rule.result.model_dump(mode="json"),
        "explanation_template": rule.explanation_template,
        "severity": rule.severity.value,
        "priority": rule.priority,
        "evidence_refs_json": rule.evidence_refs,
        "applicability_json": rule.applicability.model_dump(mode="json"),
        "thresholds_json": [item.model_dump(mode="json") for item in rule.thresholds],
        "version": rule.version,
        "current_version": rule.version,
        "lifecycle_status": rule.lifecycle_status.value,
        "enabled": rule.enabled,
        "public": rule.public,
        "source_type": rule.source_type.value,
    }


def validate_repository(root: Path) -> tuple[int, int]:
    items, rules = load_repository(root)
    return len(items), len(rules)


def sync_repository(db: Session, root: Path) -> dict[str, int]:
    try:
        items, rules = load_repository(root)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    counters = {
        "added_items": 0,
        "updated_items": 0,
        "skipped_items": 0,
        "added_rules": 0,
        "updated_rules": 0,
        "skipped_rules": 0,
    }
    with db.begin_nested():
        for item in items:
            payload = _knowledge_payload(item)
            existing = db.scalar(select(TrainingKnowledgeItem).where(TrainingKnowledgeItem.code == item.code))
            if existing is None:
                db.add(TrainingKnowledgeItem(**payload))
                counters["added_items"] += 1
                continue
            current = {key: getattr(existing, key) for key in payload}
            if existing.version == item.version and current != payload:
                raise BadRequestError(f"Knowledge item {item.code} changed without version bump.")
            if _semver_key(item.version) > _semver_key(existing.version):
                for key, value in payload.items():
                    setattr(existing, key, value)
                counters["updated_items"] += 1
            else:
                counters["skipped_items"] += 1
        for rule in rules:
            payload = _rule_payload(rule)
            existing = db.scalar(select(TrainingRule).where(TrainingRule.code == rule.code))
            if existing is None:
                db.add(TrainingRule(**payload))
                counters["added_rules"] += 1
                continue
            compare_payload = dict(payload)
            compare_payload["enabled"] = existing.enabled
            for governance_key in ("current_version", "lifecycle_status", "applicability_json"):
                compare_payload.pop(governance_key, None)
            current = {key: getattr(existing, key) for key in compare_payload}
            if existing.version == rule.version and current != compare_payload:
                raise BadRequestError(f"Training rule {rule.code} changed without version bump.")
            if _semver_key(rule.version) > _semver_key(existing.version):
                for key, value in payload.items():
                    if key == "enabled":
                        continue
                    setattr(existing, key, value)
                counters["updated_rules"] += 1
            else:
                counters["skipped_rules"] += 1
    db.commit()
    return counters
