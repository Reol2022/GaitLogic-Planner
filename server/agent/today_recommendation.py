from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from server.agent.errors import AgentErrorCode
from server.agent.schemas import AgentContext, AgentModelOutput

_FORBIDDEN_MEDICAL = re.compile(
    r"(?i)(diagnos(?:e|is)|you have (?:an? )?(?:injury|disease)|确诊|诊断为|患有)"
)
_ABSOLUTE_SAFETY = re.compile(r"(?i)(absolutely safe|completely safe|零风险|绝对安全|完全安全)")
_PLAN_MUTATION = re.compile(
    r"(?i)(i (?:have )?(?:changed|updated|modified) your (?:training )?plan|已(?:为你)?(?:修改|调整|更新)(?:了)?(?:训练)?计划)"
)
_HIGH_INTENSITY = re.compile(r"(?i)(high[- ]intensity|intervals?|sprint|高强度|间歇|冲刺)")
_NUMBER_WITH_TRAINING_UNIT = re.compile(
    r"(?i)(\d+(?:\.\d+)?)\s*(km|kilometers?|minutes?|min|公里|分钟)"
)


def canonical_today_decision(evaluation: dict[str, Any] | None) -> str:
    if not evaluation or evaluation.get("data_status") in {"UNKNOWN", "NOT_FOUND"}:
        return "UNKNOWN"
    source = str(evaluation.get("decision") or "UNKNOWN")
    if source in {
        "PROCEED",
        "PROCEED_WITH_CAUTION",
        "CONSIDER_ADJUSTMENT",
        "REST_OR_RECOVERY",
        "UNKNOWN",
    }:
        return source
    if source == "passed":
        return "PROCEED"
    if source == "passed_with_notice":
        return "PROCEED_WITH_CAUTION"
    if source in {"adjustment_recommended", "auto_apply_blocked"}:
        return "CONSIDER_ADJUSTMENT"
    if source == "needs_review":
        actions = {
            str(hit.get("action"))
            for hit in evaluation.get("rule_hits", [])
            if isinstance(hit, dict)
        }
        return "REST_OR_RECOVERY" if "rest_recommended" in actions else "CONSIDER_ADJUSTMENT"
    return "UNKNOWN"


def contextual_evidence(context: AgentContext) -> list[str]:
    evidence: list[str] = []
    evaluation = context.today_evaluation or {}
    evidence.extend(str(item) for item in evaluation.get("evidence", []) if item)
    for hit in evaluation.get("rule_hits", []):
        if isinstance(hit, dict):
            evidence.extend(
                str(item)
                for item in (hit.get("rule_code"), hit.get("explanation"))
                if item
            )
    state = context.runner_state or {}
    for item in state.get("evidence", []):
        if isinstance(item, dict) and item.get("metric"):
            evidence.append(str(item["metric"]))
    return list(dict.fromkeys(evidence))


@dataclass(frozen=True)
class EvidenceCatalogItem:
    """One request-local reference to canonical Evidence text."""

    id: str
    text: str


def build_evidence_catalog(context: AgentContext) -> list[EvidenceCatalogItem]:
    return [
        EvidenceCatalogItem(id=f"evidence_{index}", text=text)
        for index, text in enumerate(contextual_evidence(context), start=1)
    ]


def materialize_evidence_references(
    evidence_ids: list[str],
    context: AgentContext,
) -> list[str]:
    """Resolve exact request-local IDs in canonical source order."""

    catalog = build_evidence_catalog(context)
    if catalog and not evidence_ids:
        raise ValueError("at least one Evidence reference is required")
    if len(evidence_ids) > len(catalog) or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Evidence references are duplicated or exceed the catalog")
    by_id = {item.id: item for item in catalog}
    if any(
        not isinstance(item, str)
        or item.strip() != item
        or item not in by_id
        for item in evidence_ids
    ):
        raise ValueError("Evidence reference does not exist in this request")
    selected = set(evidence_ids)
    return [item.text for item in catalog if item.id in selected]


def _numbers(value: Any) -> set[float]:
    found: set[float] = set()
    if isinstance(value, bool):
        return found
    if isinstance(value, (int, float)):
        found.add(round(float(value), 4))
    elif isinstance(value, list):
        for item in value:
            found.update(_numbers(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.update(_numbers(item))
    return found


class TodayRecommendationValidator:
    """Deterministically enforces the authority of plan and rule tool results."""

    def validate(self, output: AgentModelOutput, context: AgentContext) -> list[AgentErrorCode]:
        recommendation = output.today_recommendation
        if recommendation is None:
            return [AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID]
        errors: list[AgentErrorCode] = []
        expected_decision = canonical_today_decision(context.today_evaluation)
        planned_status = str((context.today_workout or {}).get("workout_status") or "UNKNOWN")
        if recommendation.decision != expected_decision:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if recommendation.planned_workout_status != planned_status:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        expected_quality = str((context.data_quality or {}).get("data_status") or "UNKNOWN")
        if recommendation.data_quality != expected_quality:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if context.missing_reasons and not output.limitations:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if expected_decision == "UNKNOWN" and not output.limitations:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        risk = str((context.today_evaluation or {}).get("risk_level") or "UNKNOWN")
        if risk == "HIGH" and not output.warnings:
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        text = "\n".join(
            [output.answer or "", recommendation.headline, *recommendation.key_evidence]
        )
        if _FORBIDDEN_MEDICAL.search(text) or _ABSOLUTE_SAFETY.search(text):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if _PLAN_MUTATION.search(text):
            errors.append(AgentErrorCode.AGENT_TOOL_NOT_ALLOWED)
        if recommendation.decision == "REST_OR_RECOVERY" and _HIGH_INTENSITY.search(text):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
        if planned_status in {"NO_PLAN", "CYCLE_NOT_ACTIVE", "REST_DAY"} and _NUMBER_WITH_TRAINING_UNIT.search(text):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        allowed_evidence = set(contextual_evidence(context))
        if any(item not in allowed_evidence for item in recommendation.key_evidence):
            errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)

        allowed_numbers = _numbers(context.model_dump(mode="json"))
        for match in _NUMBER_WITH_TRAINING_UNIT.finditer(text):
            if round(float(match.group(1)), 4) not in allowed_numbers:
                errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
                break
        return list(dict.fromkeys(errors))
