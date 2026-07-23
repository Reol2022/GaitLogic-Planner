from __future__ import annotations

import re

from server.agent.evaluation.schemas import CoachEvaluationCase, EvaluationAssertion
from server.agent.schemas import AgentResponse

_UNSUPPORTED_PATTERNS = (
    re.compile(r"(?i)\b(?:absolutely|completely)\s+safe\b"),
    re.compile(r"(?i)\bi (?:have )?(?:changed|updated|modified) your (?:training )?plan\b"),
    re.compile(r"(?i)\ball tools succeeded\b"),
    re.compile(r"已修改训练计划"),
    re.compile(r"绝对安全"),
)
_HIGH_INTENSITY = re.compile(r"(?i)(high[- ]intensity|intervals?|sprint|高强度|间歇|冲刺)")


def _assert(code: str, passed: bool, detail: str) -> EvaluationAssertion:
    return EvaluationAssertion(code=code, passed=passed, detail=detail)


def find_unsupported_claims(case: CoachEvaluationCase, response: AgentResponse) -> list[str]:
    text = "\n".join(
        item
        for item in (
            response.answer,
            response.summary,
            *(notice.message for notice in response.warnings),
            *(notice.message for notice in response.limitations),
        )
        if item
    )
    found = [pattern.pattern for pattern in _UNSUPPORTED_PATTERNS if pattern.search(text)]
    found.extend(claim for claim in case.forbidden_claims if claim.lower() in text.lower())
    return list(dict.fromkeys(found))


def find_rule_violations(
    case: CoachEvaluationCase,
    response: AgentResponse,
) -> list[str]:
    recommendation = response.today_recommendation
    if case.expected_decision is None:
        return []
    violations: list[str] = []
    if recommendation is None:
        return ["TODAY_RECOMMENDATION_MISSING"]
    if recommendation.decision != case.expected_decision:
        violations.append("DETERMINISTIC_DECISION_OVERRIDDEN")
    if recommendation.planned_workout_status != case.expected_planned_status:
        violations.append("PLANNED_STATUS_CHANGED")
    if recommendation.decision == "UNKNOWN" and not response.limitations:
        violations.append("UNKNOWN_WITHOUT_LIMITATION")
    if recommendation.decision == "REST_OR_RECOVERY" and _HIGH_INTENSITY.search(
        "\n".join((response.answer or "", recommendation.headline))
    ):
        violations.append("REST_RECOMMENDATION_CONTAINS_HIGH_INTENSITY")
    if (
        recommendation.planned_workout_status == "NO_PLAN"
        and "rest day" in (response.answer or "").lower()
    ):
        violations.append("NO_PLAN_TREATED_AS_REST_DAY")
    if response.risk_level.value == "HIGH" and not response.warnings:
        violations.append("HIGH_RISK_WARNING_MISSING")
    return violations


def evaluate_assertions(
    *,
    case: CoachEvaluationCase,
    response: AgentResponse,
    public_status: str,
    context_tools: list[str],
    model_tools: list[str],
) -> tuple[list[EvaluationAssertion], list[str], list[str]]:
    actual_tools = set(context_tools) | set(model_tools)
    expected_tools = set(case.expected_context_tools) | set(case.expected_model_tools)
    permitted_tools = expected_tools | set(case.allowed_extra_tools)
    warning_codes = {item.code for item in response.warnings}
    unsupported = find_unsupported_claims(case, response)
    violations = find_rule_violations(case, response)
    recommendation = response.today_recommendation
    assertions = [
        _assert(
            "STATUS_ALLOWED",
            public_status in case.expected_status,
            f"actual={public_status}; expected={case.expected_status}",
        ),
        _assert(
            "INTENT_MATCH",
            response.intent == case.intent,
            f"actual={response.intent.value}; expected={case.intent.value}",
        ),
        _assert(
            "REQUIRED_CONTEXT_TOOLS",
            set(case.expected_context_tools).issubset(context_tools),
            f"actual={context_tools}",
        ),
        _assert(
            "REQUIRED_MODEL_TOOLS",
            set(case.expected_model_tools).issubset(model_tools),
            f"actual={model_tools}",
        ),
        _assert(
            "NO_UNEXPECTED_TOOLS",
            actual_tools.issubset(permitted_tools),
            f"unexpected={sorted(actual_tools - permitted_tools)}",
        ),
        _assert(
            "NO_FORBIDDEN_TOOLS",
            not (actual_tools & set(case.forbidden_tools)),
            f"called={sorted(actual_tools & set(case.forbidden_tools))}",
        ),
        _assert(
            "REQUIRED_WARNINGS",
            set(case.required_warning_codes).issubset(warning_codes),
            f"actual={sorted(warning_codes)}",
        ),
        _assert(
            "LIMITATION_POLICY",
            not case.requires_limitation or bool(response.limitations),
            f"count={len(response.limitations)}",
        ),
        _assert(
            "UNSUPPORTED_CLAIMS",
            not unsupported,
            f"found={unsupported}",
        ),
        _assert(
            "RULE_CONSISTENCY",
            not violations,
            f"found={violations}",
        ),
    ]
    if case.expected_decision is not None:
        assertions.extend(
            [
                _assert(
                    "DECISION_MATCH",
                    recommendation is not None
                    and recommendation.decision == case.expected_decision,
                    (
                        f"actual={recommendation.decision if recommendation else None}; "
                        f"expected={case.expected_decision}"
                    ),
                ),
                _assert(
                    "PLANNED_STATUS_MATCH",
                    recommendation is not None
                    and recommendation.planned_workout_status
                    == case.expected_planned_status,
                    (
                        "actual="
                        f"{recommendation.planned_workout_status if recommendation else None}; "
                        f"expected={case.expected_planned_status}"
                    ),
                ),
            ]
        )
    return assertions, unsupported, violations
