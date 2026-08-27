from __future__ import annotations

from dataclasses import dataclass

from server.agent.competition_ablation.schemas import (
    AblationConfig,
    AblationProviderOutput,
    CompetitionAblationCase,
)


@dataclass(frozen=True)
class PreparedAblationInput:
    payload: dict[str, object]
    tool_names: list[str]
    reflect_tool_names: list[str]
    reflect_resolved_domains: list[str]
    no_gain_reflect: bool


_DERIVED_KEYS = {
    "canonical_rules",
    "knowledge_references",
    "domain_readiness",
    "limitations",
}


def prepare_ablation_input(
    case: CompetitionAblationCase,
    config: AblationConfig,
) -> PreparedAblationInput:
    raw_facts = {
        key: value for key, value in case.facts.items() if key not in _DERIVED_KEYS
    }
    payload: dict[str, object] = {"facts": raw_facts}
    initial_tools: list[str] = []
    reflect_tools: list[str] = []
    resolved_domains: list[str] = []
    no_gain = False

    if config.tools_enabled:
        initial_tools = list(dict.fromkeys(case.expected_tool_behavior.initial_tools))
        payload["canonical_tool_results"] = {
            name: {"status": "SUCCEEDED", "fact_ids": sorted(raw_facts)}
            for name in initial_tools
        }
    if config.rules_enabled:
        payload["canonical_rules"] = case.facts.get("canonical_rules", [])
    if config.rag_enabled:
        payload["knowledge_references"] = case.facts.get("knowledge_references", [])
    if config.decision_readiness_enabled:
        payload["decision_readiness"] = case.facts.get("domain_readiness", {})
        payload["limitations"] = case.facts.get("limitations", [])
    if config.evidence_judge_enabled:
        payload["evidence_relations"] = case.evidence_relations

    if config.reflect_enabled and case.expected_reflect_behavior.should_trigger:
        candidates = list(dict.fromkeys(case.expected_tool_behavior.reflect_tools))
        reflect_tools = [name for name in candidates if name not in initial_tools]
        if case.expected_reflect_behavior.resolvable and reflect_tools:
            before = dict(raw_facts)
            raw_facts.update(case.reflect_facts)
            payload["facts"] = raw_facts
            resolved_domains = list(
                case.expected_reflect_behavior.expected_resolution_domains
            )
            readiness = payload.get("decision_readiness")
            if isinstance(readiness, dict):
                payload["decision_readiness"] = {
                    **readiness,
                    **{domain: "PARTIAL" for domain in resolved_domains},
                }
            no_gain = before == raw_facts
        else:
            no_gain = True
        payload["reflect"] = {
            "attempted_tools": reflect_tools,
            "resolved_domains": resolved_domains,
            "stopped": True,
            "no_gain": no_gain,
        }
    return PreparedAblationInput(
        payload=payload,
        tool_names=initial_tools,
        reflect_tool_names=reflect_tools,
        reflect_resolved_domains=resolved_domains,
        no_gain_reflect=no_gain,
    )


def enforce_validator(
    *,
    case: CompetitionAblationCase,
    payload: dict[str, object],
    output: AblationProviderOutput,
) -> tuple[AblationProviderOutput, list[str]]:
    """Apply bounded production safety invariants to experimental output.

    This adapter does not add a new product rule. It enforces the same public
    invariants used by Agent validation: no blocked-domain certainty, no
    conflict overclaim, no fabricated source and no unauthorised plan apply.
    """

    codes: list[str] = []
    readiness = payload.get("decision_readiness")
    readiness = readiness if isinstance(readiness, dict) else {}
    blocked_domains = {
        domain for domain, value in readiness.items() if str(value) == "BLOCKED"
    }
    relations = payload.get("evidence_relations")
    conflict_domains = {
        str(item.get("domain"))
        for item in relations or []
        if isinstance(item, dict) and item.get("type") == "conflict"
    }
    safe_decisions = []
    for decision in output.decisions:
        if decision.domain in blocked_domains:
            codes.append("BLOCKED_DOMAIN_DECISION_REJECTED")
            continue
        if decision.domain in conflict_domains and decision.certainty == "ABSOLUTE":
            codes.append("CONFLICT_OVERCLAIM_REJECTED")
            safe_decisions.append(decision.model_copy(update={"certainty": "LIMITED"}))
            continue
        safe_decisions.append(decision)

    answer_lower = output.answer.lower()
    forbidden = [
        claim
        for claim in case.expected_forbidden_claims
        if claim.lower() in answer_lower
    ]
    plan_mutation_claimed = any(
        marker in answer_lower
        for marker in (
            "i updated your official training plan",
            "i changed your official training plan",
            "已修改训练计划",
            "已应用计划",
        )
    )
    source_markers = ("http://", "https://", "doi:", "according to a study")
    source_hallucinated = any(marker in answer_lower for marker in source_markers)
    proposal_status = output.proposal_status
    if case.task_type == "PROPOSAL" and case.proposal_expected_status == "BLOCKED":
        if proposal_status != "BLOCKED":
            codes.append("UNAUTHORIZED_PROPOSAL_REJECTED")
        proposal_status = "BLOCKED"
    answer = output.answer
    completed = output.completed
    if forbidden or source_hallucinated or plan_mutation_claimed:
        codes.append("UNSUPPORTED_OUTPUT_REJECTED")
        answer = "The deterministic validator rejected an unsupported response."
        completed = False
        safe_decisions = []
    warnings = list(dict.fromkeys([*output.warning_codes, *case.expected_required_warnings]))
    limitations = list(output.limitation_codes)
    if blocked_domains and "BLOCKED_DOMAIN_LIMITATION" not in limitations:
        limitations.append("BLOCKED_DOMAIN_LIMITATION")
    return (
        output.model_copy(
            update={
                "answer": answer,
                "completed": completed,
                "decisions": safe_decisions,
                "warning_codes": warnings,
                "limitation_codes": limitations,
                "proposal_status": proposal_status,
            }
        ),
        list(dict.fromkeys(codes)),
    )
