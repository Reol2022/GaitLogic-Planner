from __future__ import annotations

from planner_core.training_knowledge.enums import ACTION_STRICTNESS, SEVERITY_WEIGHT
from planner_core.training_knowledge.schemas import ConflictResolution, EngineEvaluationResult, RuleHit


def sort_hits(hits: list[RuleHit]) -> list[RuleHit]:
    return sorted(
        hits,
        key=lambda hit: (
            -SEVERITY_WEIGHT.get(hit.severity, 0),
            -hit.priority,
            hit.rule_code,
        ),
    )


def resolve_conflicts(
    context_type: str,
    hits: list[RuleHit],
    engine_version: str,
    ruleset_version: str,
) -> EngineEvaluationResult:
    sorted_hits = sort_hits(hits)
    dominant = sorted_hits[0] if sorted_hits else None
    final_action = "no_action"
    conflict_types: set[str] = set()
    for hit in sorted_hits:
        if ACTION_STRICTNESS.get(hit.action, 0) > ACTION_STRICTNESS.get(final_action, 0):
            if final_action != "no_action":
                conflict_types.add("different_action_escalated")
            final_action = hit.action
    if len(sorted_hits) > 1:
        actions = {hit.action for hit in sorted_hits}
        severities = {hit.severity for hit in sorted_hits}
        priorities = {hit.priority for hit in sorted_hits}
        conflict_types.add("same_action" if len(actions) == 1 else "different_action_compatible")
        if len(severities) < len(sorted_hits):
            conflict_types.add("severity_tie")
        if len(priorities) < len(sorted_hits):
            conflict_types.add("priority_tie")
        if "keep_plan" in actions and any(action in actions for action in {"downgrade_recommended", "rest_recommended", "adjust_recommended"}):
            conflict_types.add("opposite_recommendation")
        if "rest_recommended" in actions and "adjust_recommended" in actions:
            conflict_types.add("opposite_recommendation")
    recommendations: list[str] = []
    seen: set[str] = set()
    for hit in sorted_hits:
        if hit.recommendation and hit.recommendation not in seen:
            recommendations.append(hit.recommendation)
            seen.add(hit.recommendation)
    manual_review = "opposite_recommendation" in conflict_types and final_action != "block_auto_apply"
    if manual_review:
        final_action = "require_user_review"
    return EngineEvaluationResult(
        context_type=context_type,
        final_action=final_action,
        dominant_rule_code=dominant.rule_code if dominant else None,
        matched_rule_codes=[hit.rule_code for hit in sorted_hits],
        matched_rules=sorted_hits,
        conflict_resolution=ConflictResolution(
            conflict_types=sorted(conflict_types),
            conflict_requires_manual_review=manual_review,
        ),
        recommendations=recommendations,
        engine_version=engine_version,
        ruleset_version=ruleset_version,
    )
