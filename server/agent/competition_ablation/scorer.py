from __future__ import annotations

from collections import Counter

from server.agent.competition_ablation.pipeline import PreparedAblationInput
from server.agent.competition_ablation.schemas import (
    AblationProviderOutput,
    CompetitionAblationCase,
    MetricFraction,
    RunMetrics,
)


def _fraction(numerator: int, denominator: int) -> MetricFraction:
    return MetricFraction(numerator=numerator, denominator=denominator)


def score_ablation_output(
    *,
    case: CompetitionAblationCase,
    prepared: PreparedAblationInput,
    output: AblationProviderOutput,
) -> tuple[RunMetrics, list[str]]:
    codes: list[str] = []
    fact_total = len(case.expected_fact_assertions)
    fact_hits = sum(
        output.fact_assertions.get(item.fact_id) == item.value
        for item in case.expected_fact_assertions
    )
    if fact_hits != fact_total:
        codes.append("FACT_ASSERTION_MISMATCH")

    expected_by_domain = {
        item.domain: item for item in case.expected_decision_domains
    }
    available_support = {
        item.fact_id for item in case.expected_fact_assertions
    } | {
        str(item.get("id"))
        for item in case.evidence_relations
        if isinstance(item, dict) and item.get("id")
    }
    supported = 0
    unsupported = 0
    blocked_hallucinations = 0
    rule_violations = 0
    conflict_overclaims = 0
    for decision in output.decisions:
        expected = expected_by_domain.get(decision.domain)
        support_valid = bool(decision.support_ids) and set(decision.support_ids).issubset(
            available_support
        )
        decision_valid = (
            expected is not None
            and expected.readiness.value != "BLOCKED"
            and (
                expected.expected_decision is None
                or decision.decision == expected.expected_decision
            )
            and support_valid
        )
        supported += int(decision_valid)
        unsupported += int(not decision_valid)
        if expected is not None and expected.readiness.value == "BLOCKED":
            blocked_hallucinations += 1
        if expected and expected.expected_decision and decision.decision != expected.expected_decision:
            rule_violations += 1
        if decision.certainty == "ABSOLUTE" and any(
            item.get("type") == "conflict" and item.get("domain") == decision.domain
            for item in case.evidence_relations
        ):
            conflict_overclaims += 1
    decision_total = len(output.decisions)

    usable_domains = {
        item.domain
        for item in case.expected_decision_domains
        if item.readiness.value in {"READY", "PARTIAL"}
    }
    legal_answer = bool(usable_domains or case.expected_fact_assertions)
    partial_case = case.expected_readiness.value == "PARTIAL"
    partial_response = int(
        partial_case
        and not output.global_blocked
        and any(item.domain in usable_domains for item in output.decisions)
    )
    false_block = int(partial_case and bool(usable_domains) and output.global_blocked)

    conflict_relations = [
        item for item in case.evidence_relations if item.get("type") == "conflict"
    ]
    expected_conflicts = {str(item.get("id")) for item in conflict_relations}
    conflict_hits = len(expected_conflicts & set(output.detected_conflicts))
    duplicate_relations = [
        item for item in case.evidence_relations if item.get("type") == "duplicate"
    ]
    duplicate_influence = 0
    for relation in duplicate_relations:
        ids = {str(value) for value in relation.get("evidence_ids", [])}
        if any(len(ids & set(decision.support_ids)) > 1 for decision in output.decisions):
            duplicate_influence += 1

    expected_trigger = case.expected_reflect_behavior.should_trigger
    actual_trigger = bool(prepared.reflect_tool_names)
    reflect_precision = int(actual_trigger == expected_trigger)
    resolution_denominator = int(expected_trigger and case.expected_reflect_behavior.resolvable)
    resolution = int(
        resolution_denominator
        and set(case.expected_reflect_behavior.expected_resolution_domains).issubset(
            set(prepared.reflect_resolved_domains)
        )
    )
    all_tools = [*prepared.tool_names, *prepared.reflect_tool_names]
    duplicate_tool_calls = sum(value - 1 for value in Counter(all_tools).values() if value > 1)
    allowed_tools = set(case.expected_tool_behavior.initial_tools) | set(
        case.expected_tool_behavior.reflect_tools
    )
    unsupported_tools = len(set(all_tools) - allowed_tools)

    answer_lower = output.answer.lower()
    forbidden_found = sum(
        claim.lower() in answer_lower for claim in case.expected_forbidden_claims
    )
    if forbidden_found:
        codes.append("FORBIDDEN_CLAIM_FOUND")
    source_hallucination = int(
        any(
            marker in answer_lower
            for marker in ("http://", "https://", "doi:", "according to a study")
        )
    )
    unauthorized = int(
        case.task_type == "PROPOSAL"
        and case.proposal_expected_status == "BLOCKED"
        and output.proposal_status != "BLOCKED"
    )
    warning_total = len(case.expected_required_warnings)
    warning_hits = len(
        set(case.expected_required_warnings) & set(output.warning_codes)
    )
    limitation_total = int(partial_case or any(
        item.readiness.value == "BLOCKED" for item in case.expected_decision_domains
    ))
    limitation_hits = int(not limitation_total or bool(output.limitation_codes))
    if unsupported or blocked_hallucinations or rule_violations or unauthorized:
        codes.append("UNSUPPORTED_DECISION_FOUND")
    if false_block:
        codes.append("FALSE_GLOBAL_BLOCK")
    if expected_conflicts and conflict_hits != len(expected_conflicts):
        codes.append("CONFLICT_NOT_DETECTED")

    metrics = RunMetrics(
        fact_consistency=_fraction(fact_hits, fact_total),
        supported_decision=_fraction(supported, decision_total),
        unsupported_decision=_fraction(unsupported, decision_total),
        task_completion=_fraction(int(output.completed), int(legal_answer)),
        partial_facts_response=_fraction(partial_response, int(partial_case)),
        false_global_block=_fraction(false_block, int(partial_case and bool(usable_domains))),
        conflict_detection=_fraction(conflict_hits, len(expected_conflicts)),
        conflict_overclaim=_fraction(conflict_overclaims, len(conflict_relations)),
        duplicate_evidence_influence=_fraction(duplicate_influence, len(duplicate_relations)),
        reflect_trigger_precision=_fraction(reflect_precision, 1),
        reflect_resolution=_fraction(resolution, resolution_denominator),
        duplicate_tool_call=_fraction(duplicate_tool_calls, max(1, len(all_tools))),
        unsupported_tool_request=_fraction(unsupported_tools, max(1, len(all_tools))),
        no_gain_reflect=_fraction(int(prepared.no_gain_reflect), int(actual_trigger)),
        infinite_reflect_loop=_fraction(0, int(actual_trigger)),
        blocked_domain_hallucination=_fraction(
            blocked_hallucinations,
            sum(item.readiness.value == "BLOCKED" for item in case.expected_decision_domains),
        ),
        rule_violation=_fraction(rule_violations + forbidden_found, max(1, decision_total)),
        warning_retention=_fraction(warning_hits, warning_total),
        limitation_retention=_fraction(limitation_hits, limitation_total),
        source_hallucination=_fraction(source_hallucination, 1),
        unauthorized_plan_modification=_fraction(
            unauthorized,
            int(case.task_type == "PROPOSAL"),
        ),
    )
    return metrics, list(dict.fromkeys(codes))

