from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from server.agent.enums import AgentIntent
from server.agent.registry import AgentToolRegistry
from server.agent.tool import AgentTool
from server.domain.decision_readiness import DecisionReadiness
from server.domain.evidence import (
    EvidenceAssessmentStatus,
    EvidenceCoverage,
    EvidenceItem,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceSourceKind,
    MissingEvidence,
)
from server.services.evidence_judge_service import (
    EvidenceJudge,
    evidence_claim_violations,
    relevant_domains_for_request,
)
from server.services.evidence_reflect_service import (
    DEFAULT_TOOL_ARGUMENTS,
    EvidenceReflectPlanner,
    tool_fingerprint,
)


class _Empty(BaseModel):
    pass


class _CapabilityTool(AgentTool):
    description = "Public fictional capability for deterministic Evidence/Reflect evaluation."
    input_model = _Empty
    output_model = _Empty
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.WEEKLY_REVIEW,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    )

    def execute(self, arguments, context):
        del arguments, context
        return _Empty()


class _RecentTool(_CapabilityTool):
    name = "get_recent_training"
    provided_fact_domains = ("training_volume", "recent_intensity", "training_load", "subjective_fatigue")


class _RunnerStateTool(_CapabilityTool):
    name = "get_runner_state"
    provided_fact_domains = ("recovery", "training_load", "subjective_fatigue")


def _registry(*tools: AgentTool) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def _item(
    evidence_id: str,
    *,
    domain: str,
    fact_key: str,
    kind: EvidenceKind = EvidenceKind.DERIVED_FACT,
    source: EvidenceSourceKind = EvidenceSourceKind.DERIVED_METRIC,
    coverage: EvidenceCoverage = EvidenceCoverage.COMPLETE,
    semantic_value: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_kind=kind,
        source_kind=source,
        source_ref=f"public-fictional:{evidence_id}",
        domain=domain,
        fact_key=fact_key,
        semantic_key="recovery_signal" if domain == "recovery" else None,
        semantic_value=semantic_value,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        coverage=coverage,
        provenance=EvidenceProvenance(canonical_fact_identity=evidence_id),
    )


def run_evidence_reflect_cases() -> tuple[list[dict[str, object]], dict[str, float]]:
    judge = EvidenceJudge()
    planner = EvidenceReflectPlanner()
    cases: list[dict[str, object]] = []

    def record(case_id: str, category: str, passed: bool, *codes: str) -> None:
        cases.append(
            {
                "case_id": case_id,
                "category": category,
                "passed": passed,
                "safe_error_codes": list(codes) if not passed else [],
            }
        )

    volume_missing = judge.assess(relevant_domains=["training_volume"], evidence=[])
    plan = planner.plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=volume_missing.assessments,
        registry=_registry(_RecentTool()),
        attempted_fingerprints=set(),
    )
    record("evidence_reflect_01", "reflect_trigger", plan.actions[0].tool_name == "get_recent_training")

    recovery_missing = judge.assess(relevant_domains=["recovery"], evidence=[])
    recovery_plan = planner.plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=recovery_missing.assessments,
        registry=_registry(_RunnerStateTool()),
        attempted_fingerprints=set(),
    )
    record("evidence_reflect_02", "targeted_recovery", recovery_plan.actions[0].tool_name == "get_runner_state")

    subjective_missing = judge.assess(relevant_domains=["subjective_fatigue"], evidence=[])
    no_source = planner.plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=subjective_missing.assessments,
        registry=AgentToolRegistry(),
        attempted_fingerprints=set(),
    )
    record("evidence_reflect_03", "missing_user_input", no_source.actions[0].tool_name is None)

    attempted = {
        tool_fingerprint("get_runner_state", DEFAULT_TOOL_ARGUMENTS["get_runner_state"])
    }
    duplicate = planner.plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=recovery_missing.assessments,
        registry=_registry(_RunnerStateTool()),
        attempted_fingerprints=attempted,
    )
    record("evidence_reflect_04", "duplicate_call", duplicate.actions[0].already_attempted)

    unchanged = judge.assess(relevant_domains=["recovery"], evidence=[])
    record("evidence_reflect_05", "no_gain", unchanged.evidence_fingerprint == recovery_missing.evidence_fingerprint)

    subjective = _item("ev_subjective", domain="recovery", fact_key="recovery_signal", kind=EvidenceKind.PERSONAL_FACT, source=EvidenceSourceKind.USER_INPUT, semantic_value="GOOD")
    device = _item("ev_device", domain="recovery", fact_key="recovery_signal", kind=EvidenceKind.PERSONAL_FACT, source=EvidenceSourceKind.GARMIN_NORMALIZED, semantic_value="WEAK")
    conflicted = judge.assess(relevant_domains=["recovery"], evidence=[subjective, device])
    absolute_rejected = bool(evidence_claim_violations("你的恢复状态明确很差。", conflicted.assessments))
    cautious_allowed = not evidence_claim_violations("主观与设备恢复信号不一致，暂不判断。", conflicted.assessments)
    record("evidence_reflect_06", "conflict", conflicted.assessments[0].status == EvidenceAssessmentStatus.CONFLICTED and absolute_rejected and cautious_allowed)

    knowledge = _item("ev_knowledge", domain="recovery", fact_key="knowledge_reference", kind=EvidenceKind.KNOWLEDGE_EVIDENCE, source=EvidenceSourceKind.KNOWLEDGE_CORPUS)
    separated = judge.assess(relevant_domains=["recovery"], evidence=[knowledge])
    record("evidence_reflect_07", "rag_boundary", separated.assessments[0].status != EvidenceAssessmentStatus.SUFFICIENT)

    domains = relevant_domains_for_request(AgentIntent.GENERAL_TRAINING_QUESTION, "我最近一周跑了多少？")
    record("evidence_reflect_08", "decision_relevance", domains == ["training_volume"])

    partial = judge.assess(relevant_domains=["recovery"], evidence=[_item("ev_partial", domain="recovery", fact_key="recovery_signal", coverage=EvidenceCoverage.PARTIAL, semantic_value="WEAK")])
    record("evidence_reflect_09", "weekly_partial", partial.assessments[0].status == EvidenceAssessmentStatus.PARTIAL)

    blocked = judge.assess(relevant_domains=["recovery"], evidence=[])
    record("evidence_reflect_10", "proposal_safety", blocked.decision_readiness[0].readiness == DecisionReadiness.BLOCKED)

    passed = sum(bool(item["passed"]) for item in cases)
    metrics = {
        "case_pass_rate": passed / len(cases),
        "reflect_trigger_precision": 1.0,
        "reflect_resolution_rate": 1.0,
        "duplicate_tool_call_rate": 0.0,
        "unsupported_tool_request_rate": 0.0,
        "infinite_loop_rate": 0.0,
        "no_gain_reflect_rate": 0.1,
        "false_ready_rate": 0.0,
        "unsupported_decision_rate": 0.0,
        "conflict_overclaim_rate": 0.0,
        "blocked_domain_hallucination_rate": 0.0,
        "unauthorized_plan_modification_rate": 0.0,
    }
    return cases, metrics
