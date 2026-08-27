from __future__ import annotations

import hashlib
import json
from typing import Iterable

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext, AgentToolResult
from server.domain.evidence import (
    EvidenceAssessment,
    EvidenceAssessmentStatus,
    MissingEvidencePlan,
    ReflectAction,
)


DEFAULT_TOOL_ARGUMENTS: dict[str, dict[str, object]] = {
    "get_runner_state": {},
    "get_runner_state_history": {"limit": 7},
    "get_recent_training": {"days": 7, "limit": 20},
    "get_today_workout": {},
    "get_current_training_cycle": {},
    "get_training_rules": {"scope": "GENERAL"},
    "evaluate_today_workout": {},
    "get_training_data_quality": {"window_days": 14},
    "retrieve_training_knowledge": {},
}


def tool_fingerprint(tool_name: str, arguments: dict[str, object]) -> str:
    payload = json.dumps({"tool_name": tool_name, "arguments": arguments}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def successful_tool_fingerprints(results: Iterable[AgentToolResult]) -> set[str]:
    # Existing AgentToolResult intentionally does not expose arguments.  The
    # registered tools used by Reflect have one canonical bounded argument set.
    return {
        tool_fingerprint(result.tool_name, DEFAULT_TOOL_ARGUMENTS.get(result.tool_name, {}))
        for result in results
        if result.status == AgentToolStatus.SUCCEEDED
    }


class EvidenceReflectPlanner:
    """Deterministic missing-evidence planner; it never calls an LLM."""

    def plan(
        self,
        *,
        intent: AgentIntent,
        assessments: Iterable[EvidenceAssessment],
        registry: AgentToolRegistry,
        attempted_fingerprints: set[str],
    ) -> MissingEvidencePlan:
        definitions = {item.name: item for item in registry.list_tools(intent)}
        actions: list[ReflectAction] = []
        stop_reasons: list[str] = []
        reserved_fingerprints = set(attempted_fingerprints)
        for domain_index, assessment in enumerate(assessments):
            if assessment.status not in {EvidenceAssessmentStatus.MISSING, EvidenceAssessmentStatus.PARTIAL}:
                continue
            for missing in assessment.missing_evidence:
                candidates = [name for name in missing.candidate_tools if name in definitions]
                selected: ReflectAction | None = None
                for name in candidates:
                    definition = definitions[name]
                    if assessment.domain not in definition.provided_fact_domains:
                        continue
                    arguments = dict(DEFAULT_TOOL_ARGUMENTS.get(name, {}))
                    if name == "retrieve_training_knowledge":
                        continue
                    fingerprint = tool_fingerprint(name, arguments)
                    attempted = fingerprint in reserved_fingerprints
                    candidate = ReflectAction(
                        target_domain=assessment.domain,
                        missing_fact="|".join(missing.fact_keys),
                        tool_name=name,
                        arguments=arguments,
                        reason=f"{assessment.domain} lacks {missing.description}",
                        priority=min(100, 10 + domain_index),
                        automatically_resolvable=not attempted,
                        already_attempted=attempted,
                        fingerprint=fingerprint,
                    )
                    if not attempted:
                        selected = candidate
                        reserved_fingerprints.add(fingerprint)
                        break
                    if selected is None:
                        selected = candidate
                if selected is not None:
                    actions.append(selected)
                else:
                    actions.append(
                        ReflectAction(
                            target_domain=assessment.domain,
                            missing_fact="|".join(missing.fact_keys),
                            reason=f"No allowed registered tool can provide {missing.description}",
                            priority=min(100, 10 + domain_index),
                            automatically_resolvable=False,
                        )
                    )
        executable = [item for item in actions if item.automatically_resolvable and not item.already_attempted and item.tool_name]
        if not actions:
            stop_reasons.append("EVIDENCE_ALREADY_SUFFICIENT")
        elif not executable:
            stop_reasons.append("NO_AUTOMATIC_EVIDENCE_SOURCE")
        return MissingEvidencePlan(actions=actions, stop_reasons=stop_reasons)


def execute_reflect_actions(
    *,
    plan: MissingEvidencePlan,
    registry: AgentToolRegistry,
    context: AgentContext,
    max_actions: int,
) -> tuple[list[AgentToolResult], set[str]]:
    results: list[AgentToolResult] = []
    fingerprints: set[str] = set()
    for action in plan.actions:
        if len(results) >= max_actions:
            break
        if not action.automatically_resolvable or action.already_attempted or not action.tool_name or not action.fingerprint:
            continue
        if action.fingerprint in fingerprints:
            continue
        fingerprints.add(action.fingerprint)
        results.append(registry.invoke(action.tool_name, action.arguments, context))
        if results[-1].status != AgentToolStatus.SUCCEEDED:
            break
    return results, fingerprints
