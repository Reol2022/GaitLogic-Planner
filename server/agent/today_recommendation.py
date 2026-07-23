from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from server.agent.enums import AgentRiskLevel
from server.agent.errors import AgentErrorCode
from server.agent.schemas import (
    AgentContext,
    AgentModelOutput,
    AgentNotice,
    AgentTodayRecommendation,
)

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


@dataclass(frozen=True)
class AuthoritativeTodayFacts:
    risk_level: AgentRiskLevel
    recommendation: AgentTodayRecommendation
    warnings: list[AgentNotice]
    limitations: list[AgentNotice]


def _is_chinese(value: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in value)


def _notices_from(value: Any, field: str) -> list[AgentNotice]:
    if not isinstance(value, dict):
        return []
    notices = value.get(field, [])
    if not isinstance(notices, list):
        return []
    return [
        AgentNotice.model_validate(item)
        for item in notices
        if isinstance(item, dict)
    ]


def _unique_notices(values: list[AgentNotice]) -> list[AgentNotice]:
    unique: list[AgentNotice] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        key = (item.code, item.message)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:20]


def build_authoritative_today_facts(
    context: AgentContext,
    *,
    user_message: str,
    key_evidence: list[str] | None = None,
) -> AuthoritativeTodayFacts:
    """Build every deterministic TODAY field from validated server context."""

    evaluation = context.today_evaluation or {}
    decision = canonical_today_decision(evaluation)
    planned_value = (context.today_workout or {}).get("workout_status")
    planned_status = (
        planned_value
        if isinstance(planned_value, str)
        and planned_value
        in {"PLANNED", "REST_DAY", "NO_PLAN", "CYCLE_NOT_ACTIVE", "UNKNOWN"}
        else "UNKNOWN"
    )
    risk_value = evaluation.get("risk_level")
    risk = (
        AgentRiskLevel(risk_value)
        if isinstance(risk_value, str)
        and risk_value in AgentRiskLevel._value2member_map_
        else AgentRiskLevel.UNKNOWN
    )
    quality_value = (context.data_quality or {}).get("data_status")
    quality = quality_value if isinstance(quality_value, str) and quality_value else "UNKNOWN"
    chinese = _is_chinese(user_message)
    headline_map = {
        "PROCEED": "可以按原计划执行。" if chinese else "Proceed with the existing plan.",
        "PROCEED_WITH_CAUTION": (
            "建议谨慎执行原计划。"
            if chinese
            else "Proceed cautiously with the existing plan."
        ),
        "CONSIDER_ADJUSTMENT": (
            "建议考虑调整，但系统没有修改计划。"
            if chinese
            else "Consider an adjustment; no plan was changed."
        ),
        "REST_OR_RECOVERY": (
            "规则建议休息或恢复。"
            if chinese
            else "The rules recommend rest or recovery."
        ),
        "UNKNOWN": (
            "数据不足，无法给出确定的今日建议。"
            if chinese
            else "Available data is insufficient for a definite recommendation."
        ),
    }
    sources = (
        context.today_evaluation,
        context.data_quality,
        context.today_workout,
        context.recent_training,
        context.runner_state,
    )
    warnings = _unique_notices(
        [notice for source in sources for notice in _notices_from(source, "warnings")]
    )
    limitations = _unique_notices(
        [
            *context.limitations,
            *[
                notice
                for source in sources
                for notice in _notices_from(source, "limitations")
            ],
        ]
    )
    if context.missing_reasons:
        limitations = _unique_notices(
            [
                *limitations,
                AgentNotice(
                    code="TODAY_CONTEXT_INCOMPLETE",
                    message="One or more required TODAY data sources are unavailable.",
                ),
            ]
        )
    if decision == "UNKNOWN" and not limitations:
        limitations = [
            AgentNotice(
                code="TODAY_DATA_INSUFFICIENT",
                message="Available TODAY facts are insufficient for a deterministic decision.",
            )
        ]
    if risk == AgentRiskLevel.HIGH and not warnings:
        warnings = [
            AgentNotice(
                code="HIGH_RISK_REVIEW_REQUIRED",
                message="Existing rules require manual review before training.",
            )
        ]
    evidence = (
        key_evidence
        if key_evidence is not None
        else contextual_evidence(context)[:5]
    )
    return AuthoritativeTodayFacts(
        risk_level=risk,
        recommendation=AgentTodayRecommendation(
            decision=decision,
            planned_workout_status=planned_status,
            headline=headline_map[decision],
            key_evidence=evidence,
            data_quality=quality,
        ),
        warnings=warnings,
        limitations=limitations,
    )


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
