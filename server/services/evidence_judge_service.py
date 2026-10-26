from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterable

from planner_core.weekly_review.schemas import WeeklyFacts
from server.domain.decision_readiness import DecisionReadiness, DomainReadiness
from server.domain.evidence import (
    EvidenceAssessment,
    EvidenceAssessmentStatus,
    EvidenceConflict,
    EvidenceCoverage,
    EvidenceFreshness,
    EvidenceItem,
    EvidenceJudgeResult,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceRequirement,
    EvidenceSourceKind,
    EvidenceUsability,
    MissingEvidence,
    RequiredEvidenceProfile,
)

if TYPE_CHECKING:
    from server.agent.schemas import AgentContext, AgentToolResult


_FACT_KINDS = [EvidenceKind.PERSONAL_FACT, EvidenceKind.DERIVED_FACT]


REQUIRED_EVIDENCE_PROFILES: dict[str, RequiredEvidenceProfile] = {
    "training_volume": RequiredEvidenceProfile(
        domain="training_volume",
        required=[EvidenceRequirement(fact_keys=["recent_training"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_recent_training"], description="Recent completed training facts")],
        optional_fact_keys=["training_plan_context"],
    ),
    "training_frequency": RequiredEvidenceProfile(
        domain="training_frequency",
        required=[EvidenceRequirement(fact_keys=["recent_training"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_recent_training"], description="Recent training session facts")],
    ),
    "recent_intensity": RequiredEvidenceProfile(
        domain="recent_intensity",
        required=[EvidenceRequirement(fact_keys=["recent_training"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_recent_training", "get_runner_state"], description="Recent intensity-bearing training facts")],
    ),
    "training_load": RequiredEvidenceProfile(
        domain="training_load",
        required=[EvidenceRequirement(fact_keys=["runner_state_current", "recent_training"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_runner_state", "get_recent_training"], description="Current load or recent training facts")],
    ),
    "today_plan": RequiredEvidenceProfile(
        domain="today_plan",
        required=[EvidenceRequirement(fact_keys=["today_plan"], accepted_kinds=[EvidenceKind.PERSONAL_FACT], candidate_tools=["get_today_workout"], description="Authenticated runner's current-day plan")],
    ),
    "plan_execution": RequiredEvidenceProfile(
        domain="plan_execution",
        required=[EvidenceRequirement(fact_keys=["plan_execution"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_recent_training"], description="Plan and completed-log comparison")],
    ),
    "recovery": RequiredEvidenceProfile(
        domain="recovery",
        required=[EvidenceRequirement(fact_keys=["recovery_signal"], accepted_kinds=_FACT_KINDS, candidate_tools=["get_runner_state", "get_runner_state_history"], description="Current or recent canonical recovery signal")],
        optional_fact_keys=["subjective_feedback"],
    ),
    "subjective_fatigue": RequiredEvidenceProfile(
        domain="subjective_fatigue",
        required=[EvidenceRequirement(fact_keys=["subjective_feedback"], accepted_kinds=[EvidenceKind.PERSONAL_FACT], candidate_tools=["get_recent_training", "get_runner_state"], description="Explicit RPE or subjective feedback")],
    ),
    "training_phase": RequiredEvidenceProfile(
        domain="training_phase",
        required=[EvidenceRequirement(fact_keys=["training_phase"], accepted_kinds=[EvidenceKind.PERSONAL_FACT, EvidenceKind.DERIVED_FACT], candidate_tools=["get_current_training_cycle"], description="Current cycle phase")],
    ),
    "training_knowledge": RequiredEvidenceProfile(
        domain="training_knowledge",
        required=[EvidenceRequirement(fact_keys=["knowledge_reference"], accepted_kinds=[EvidenceKind.KNOWLEDGE_EVIDENCE], candidate_tools=["retrieve_training_knowledge"], description="Canonical training-knowledge reference")],
    ),
}


_INTENT_DOMAINS = {
    "CASUAL_CONVERSATION": [],
    "TODAY_RECOMMENDATION": ["today_plan", "training_load", "recent_intensity", "recovery"],
    "EXPLAIN_RUNNER_STATE": ["training_load", "recent_intensity", "recovery", "subjective_fatigue"],
    "WEEKLY_REVIEW": ["plan_execution", "training_volume", "training_frequency", "recent_intensity", "recovery", "subjective_fatigue", "training_phase"],
    "PERSONAL_TRAINING_ANALYSIS": ["training_load", "plan_execution", "recovery", "training_phase"],
}


def relevant_domains_for_request(intent: object, message: str) -> list[str]:
    intent_value = str(getattr(intent, "value", intent))
    if intent_value in _INTENT_DOMAINS:
        return list(_INTENT_DOMAINS[intent_value])
    lowered = message.lower()
    if any(marker in lowered for marker in ("跑了多少", "跑量", "里程", "distance", "volume", "多少公里")):
        return ["training_volume"]
    if any(marker in lowered for marker in ("恢复", "疲劳", "睡眠", "hrv", "recovery", "fatigue")):
        return ["recovery", "subjective_fatigue"]
    if any(marker in lowered for marker in ("强度", "间歇", "阈值", "intensity")):
        return ["recent_intensity", "training_load", "recovery"]
    return ["training_knowledge"]


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _item(
    *,
    evidence_kind: EvidenceKind,
    source_kind: EvidenceSourceKind,
    source_ref: str,
    domain: str,
    fact_key: str,
    canonical_identity: str,
    observed_at: date | datetime | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    freshness: EvidenceFreshness = EvidenceFreshness.RECENT,
    coverage: EvidenceCoverage = EvidenceCoverage.COMPLETE,
    usability: EvidenceUsability = EvidenceUsability.USABLE,
    limitations: list[str] | None = None,
    semantic_key: str | None = None,
    semantic_value: str | None = None,
    provider: str | None = None,
    source_record_refs: list[str] | None = None,
    derived_from: list[str] | None = None,
) -> EvidenceItem:
    identity = {
        "source": source_kind.value,
        "canonical_identity": canonical_identity,
        "domain": domain,
        "fact_key": fact_key,
        "period_start": period_start,
        "period_end": period_end,
    }
    return EvidenceItem(
        evidence_id=f"ev_{_stable_hash(identity)[:32]}",
        evidence_kind=evidence_kind,
        source_kind=source_kind,
        source_ref=source_ref,
        domain=domain,
        fact_key=fact_key,
        semantic_key=semantic_key,
        semantic_value=semantic_value,
        observed_at=observed_at,
        period_start=period_start,
        period_end=period_end,
        freshness=freshness,
        coverage=coverage,
        usability=usability,
        limitation_codes=list(dict.fromkeys(limitations or [])),
        provenance=EvidenceProvenance(
            canonical_fact_identity=canonical_identity,
            source_record_refs=source_record_refs or [],
            derived_from=derived_from or [],
            provider=provider,
        ),
    )


def _status_quality(data: dict) -> tuple[EvidenceCoverage, EvidenceUsability, list[str]]:
    status = str(data.get("data_status", "AVAILABLE"))
    limitations = []
    for item in data.get("limitations", []) or []:
        if isinstance(item, dict) and item.get("code"):
            limitations.append(str(item["code"]))
        elif isinstance(item, str):
            limitations.append(item)
    if status == "AVAILABLE":
        return EvidenceCoverage.COMPLETE, EvidenceUsability.USABLE, limitations
    if status == "PARTIAL":
        return EvidenceCoverage.PARTIAL, EvidenceUsability.LIMITED, limitations
    return EvidenceCoverage.NONE, EvidenceUsability.UNUSABLE, limitations


def _date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _tool_evidence(result: AgentToolResult) -> list[EvidenceItem]:
    if str(getattr(result.status, "value", result.status)) != "SUCCEEDED" or not isinstance(result.data, dict):
        return []
    data = result.data
    coverage, usability, limitations = _status_quality(data)
    if usability == EvidenceUsability.UNUSABLE:
        return []
    call_ref = f"tool:{result.tool_name}:{result.tool_call_id}"
    items: list[EvidenceItem] = []
    if result.tool_name == "get_recent_training":
        end = _date(data.get("as_of"))
        rows = data.get("items", []) if isinstance(data.get("items"), list) else []
        start = min((_date(row.get("date")) for row in rows if isinstance(row, dict)), default=None)
        for domain, fact_key in (("training_volume", "recent_training"), ("training_frequency", "recent_training"), ("recent_intensity", "recent_training"), ("plan_execution", "plan_execution"), ("training_load", "recent_training")):
            items.append(_item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.TRAINING_LOG, source_ref=call_ref, domain=domain, fact_key=fact_key, canonical_identity=f"recent-training:{start}:{end}", period_start=start, period_end=end, coverage=coverage, usability=usability, limitations=limitations, derived_from=[str(row.get("date")) for row in rows if isinstance(row, dict)]))
        rpe_rows = [row for row in rows if isinstance(row, dict) and row.get("rpe") is not None]
        if rpe_rows:
            items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.USER_INPUT, source_ref=call_ref, domain="subjective_fatigue", fact_key="subjective_feedback", canonical_identity=f"workout-rpe:{start}:{end}", period_start=start, period_end=end, coverage=EvidenceCoverage.COMPLETE if len(rpe_rows) == len(rows) else EvidenceCoverage.PARTIAL, usability=EvidenceUsability.USABLE if len(rpe_rows) == len(rows) else EvidenceUsability.LIMITED, limitations=[] if len(rpe_rows) == len(rows) else ["RPE_COVERAGE_PARTIAL"], semantic_key="subjective_fatigue_signal", semantic_value="RECORDED", source_record_refs=[str(row.get("date")) for row in rpe_rows]))
    elif result.tool_name == "get_runner_state":
        observed = _date(data.get("as_of_date"))
        state_value = str(data.get("overall_state", "UNKNOWN")).upper()
        for domain, fact_key in (("training_load", "runner_state_current"), ("recovery", "recovery_signal"), ("recent_intensity", "runner_state_current")):
            items.append(_item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.RUNNER_STATE, source_ref=call_ref, domain=domain, fact_key=fact_key, canonical_identity=f"runner-state:{observed}", observed_at=observed, period_start=observed, period_end=observed, freshness=EvidenceFreshness.CURRENT, coverage=coverage, usability=usability, limitations=limitations, semantic_key="recovery_signal" if domain == "recovery" else None, semantic_value=state_value if domain == "recovery" else None))
        evidence_rows = data.get("evidence", []) if isinstance(data.get("evidence"), list) else []
        if any("rpe" in str(row.get("metric", "")).lower() for row in evidence_rows if isinstance(row, dict)):
            items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.USER_INPUT, source_ref=call_ref, domain="subjective_fatigue", fact_key="subjective_feedback", canonical_identity=f"runner-state-rpe:{observed}", observed_at=observed, period_start=observed, period_end=observed, freshness=EvidenceFreshness.CURRENT, coverage=coverage, usability=usability, semantic_key="subjective_fatigue_signal", semantic_value="RECORDED"))
        metrics = data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {}
        subjective = metrics.get("subjective_recovery")
        device = metrics.get("device_recovery") or metrics.get("garmin_recovery")
        if subjective is not None:
            items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.USER_INPUT, source_ref=call_ref, domain="recovery", fact_key="recovery_signal", canonical_identity=f"subjective-recovery:{observed}", observed_at=observed, period_start=observed, period_end=observed, freshness=EvidenceFreshness.CURRENT, semantic_key="recovery_signal", semantic_value=str(subjective).upper()))
        if device is not None:
            items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.GARMIN_NORMALIZED, source_ref=call_ref, domain="recovery", fact_key="recovery_signal", canonical_identity=f"garmin-recovery:{observed}", observed_at=observed, period_start=observed, period_end=observed, freshness=EvidenceFreshness.CURRENT, semantic_key="recovery_signal", semantic_value=str(device).upper(), provider="garmin"))
    elif result.tool_name == "get_runner_state_history":
        rows = data.get("items", []) if isinstance(data.get("items"), list) else []
        dates = [_date(row.get("captured_at")) for row in rows if isinstance(row, dict)]
        dates = [value for value in dates if value is not None]
        if rows:
            for domain in ("recovery", "training_load"):
                items.append(_item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.RUNNER_STATE, source_ref=call_ref, domain=domain, fact_key="recovery_signal" if domain == "recovery" else "runner_state_current", canonical_identity=f"runner-state-history:{min(dates, default=None)}:{max(dates, default=None)}", period_start=min(dates, default=None), period_end=max(dates, default=None), coverage=coverage, usability=usability, limitations=limitations, semantic_key="recovery_signal" if domain == "recovery" else None, semantic_value="HISTORY_AVAILABLE" if domain == "recovery" else None))
    elif result.tool_name == "get_today_workout":
        observed = _date(data.get("date"))
        items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.TRAINING_PLAN, source_ref=call_ref, domain="today_plan", fact_key="today_plan", canonical_identity=f"today-plan:{observed}", observed_at=observed, period_start=observed, period_end=observed, freshness=EvidenceFreshness.CURRENT, coverage=coverage, usability=usability, limitations=limitations))
    elif result.tool_name == "get_current_training_cycle" and data.get("current_phase"):
        items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.TRAINING_PLAN, source_ref=call_ref, domain="training_phase", fact_key="training_phase", canonical_identity=f"cycle:{data.get('cycle_id')}:phase", period_start=_date(data.get("start_date")), period_end=_date(data.get("end_date")), coverage=coverage, usability=usability, limitations=limitations))
    elif result.tool_name == "evaluate_today_workout":
        items.append(_item(evidence_kind=EvidenceKind.RULE_DECISION, source_kind=EvidenceSourceKind.RULE_ENGINE, source_ref=call_ref, domain="today_decision", fact_key="rule_decision", canonical_identity=f"today-rule-decision:{data.get('decision')}", freshness=EvidenceFreshness.CURRENT, coverage=coverage, usability=usability, limitations=limitations, semantic_key="today_decision", semantic_value=str(data.get("decision", "UNKNOWN"))))
    elif result.tool_name == "retrieve_training_knowledge":
        for row in data.get("results", []) if isinstance(data.get("results"), list) else []:
            if not isinstance(row, dict):
                continue
            chunk_id = str(row.get("chunk_id") or row.get("knowledge_reference_id") or "unknown")
            items.append(_item(evidence_kind=EvidenceKind.KNOWLEDGE_EVIDENCE, source_kind=EvidenceSourceKind.KNOWLEDGE_CORPUS, source_ref=call_ref, domain="training_knowledge", fact_key="knowledge_reference", canonical_identity=f"knowledge:{chunk_id}", coverage=EvidenceCoverage.COMPLETE, usability=EvidenceUsability.USABLE, limitations=[str(value) for value in row.get("limitations", [])], provider=str(row.get("source_id") or "corpus"), source_record_refs=[chunk_id]))
    return items


def materialize_agent_evidence(context: AgentContext) -> list[EvidenceItem]:
    items = [item for result in context.tool_results for item in _tool_evidence(result)]
    for code in context.missing_reasons.values():
        if code in {"recovery_day_fatigue_rule_disabled_v1", "near_zero_volume_baseline_cutoff_not_defined"}:
            items.append(_item(evidence_kind=EvidenceKind.CAPABILITY_INFORMATION, source_kind=EvidenceSourceKind.SYSTEM_CAPABILITY, source_ref="agent-context", domain="system_capability", fact_key="capability_information", canonical_identity=f"capability:{code}", coverage=EvidenceCoverage.COMPLETE, usability=EvidenceUsability.USABLE, limitations=[code]))
    return items


def materialize_weekly_evidence(facts: WeeklyFacts, supplemental_results: Iterable[AgentToolResult] = ()) -> list[EvidenceItem]:
    start, end = facts.period.week_start, facts.period.week_end
    quality_partial = bool(facts.data_quality.missing_log_fields or facts.data_quality.missing_plan_days)
    coverage = EvidenceCoverage.PARTIAL if quality_partial else EvidenceCoverage.COMPLETE
    usability = EvidenceUsability.LIMITED if quality_partial else EvidenceUsability.USABLE
    base = f"weekly-facts:{facts.result_hash}"
    items = [
        _item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.WEEKLY_FACTS, source_ref=base, domain="plan_execution", fact_key="plan_execution", canonical_identity=f"{base}:execution", period_start=start, period_end=end, coverage=coverage, usability=usability, limitations=facts.classification.data_limitations),
        _item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.WEEKLY_FACTS, source_ref=base, domain="training_volume", fact_key="recent_training", canonical_identity=f"{base}:volume", period_start=start, period_end=end, coverage=coverage, usability=usability, limitations=facts.classification.data_limitations),
        _item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.WEEKLY_FACTS, source_ref=base, domain="training_frequency", fact_key="recent_training", canonical_identity=f"{base}:frequency", period_start=start, period_end=end, coverage=coverage, usability=usability, limitations=facts.classification.data_limitations),
        _item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.WEEKLY_FACTS, source_ref=base, domain="recent_intensity", fact_key="recent_training", canonical_identity=f"{base}:intensity", period_start=start, period_end=end, coverage=coverage, usability=usability, limitations=facts.classification.data_limitations),
    ]
    if facts.runner_state_trend.sample_count and facts.runner_state_trend.recovery_trend != "UNKNOWN":
        items.append(_item(evidence_kind=EvidenceKind.DERIVED_FACT, source_kind=EvidenceSourceKind.RUNNER_STATE, source_ref=base, domain="recovery", fact_key="recovery_signal", canonical_identity=f"{base}:recovery", period_start=start, period_end=end, coverage=EvidenceCoverage.COMPLETE if facts.data_quality.runner_state_sample_count >= 5 else EvidenceCoverage.PARTIAL, usability=EvidenceUsability.USABLE if facts.data_quality.runner_state_sample_count >= 5 else EvidenceUsability.LIMITED, semantic_key="recovery_signal", semantic_value=facts.runner_state_trend.recovery_trend.upper()))
    if facts.period.training_phase:
        items.append(_item(evidence_kind=EvidenceKind.PERSONAL_FACT, source_kind=EvidenceSourceKind.TRAINING_PLAN, source_ref=base, domain="training_phase", fact_key="training_phase", canonical_identity=f"cycle:{facts.period.cycle_id}:phase:{facts.period.training_phase}", period_start=start, period_end=end))
    for code in facts.classification.rule_codes:
        items.append(_item(evidence_kind=EvidenceKind.RULE_DECISION, source_kind=EvidenceSourceKind.RULE_ENGINE, source_ref=base, domain="weekly_decision", fact_key="rule_decision", canonical_identity=f"{base}:rule:{code}", period_start=start, period_end=end, semantic_key="weekly_rule", semantic_value=code))
    for code in facts.classification.capability_limitations:
        items.append(_item(evidence_kind=EvidenceKind.CAPABILITY_INFORMATION, source_kind=EvidenceSourceKind.SYSTEM_CAPABILITY, source_ref=base, domain="system_capability", fact_key="capability_information", canonical_identity=f"capability:{code}", limitations=[code]))
    items.extend(item for result in supplemental_results for item in _tool_evidence(result))
    return items


def _overlap(a: EvidenceItem, b: EvidenceItem) -> bool:
    if a.period_start is None or a.period_end is None or b.period_start is None or b.period_end is None:
        return True
    return a.period_start <= b.period_end and b.period_start <= a.period_end


class EvidenceJudge:
    def __init__(self, profiles: dict[str, RequiredEvidenceProfile] | None = None) -> None:
        self.profiles = profiles or REQUIRED_EVIDENCE_PROFILES

    @staticmethod
    def deduplicate(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
        selected: dict[tuple[object, ...], EvidenceItem] = {}
        rank = {EvidenceUsability.UNUSABLE: 0, EvidenceUsability.LIMITED: 1, EvidenceUsability.USABLE: 2}
        for item in items:
            key = (
                item.source_kind,
                item.provenance.canonical_fact_identity,
                item.period_start,
                item.period_end,
                item.domain,
                item.fact_key,
            )
            current = selected.get(key)
            if current is None or rank[item.usability] > rank[current.usability]:
                selected[key] = item
        return sorted(selected.values(), key=lambda item: (item.domain, item.fact_key, item.evidence_id))

    @staticmethod
    def conflicts(items: list[EvidenceItem], domain: str) -> list[EvidenceConflict]:
        candidates = [item for item in items if item.domain == domain and item.semantic_key and item.semantic_value and item.usability != EvidenceUsability.UNUSABLE]
        found: dict[tuple[str, tuple[str, ...]], EvidenceConflict] = {}
        for index, left in enumerate(candidates):
            for right in candidates[index + 1:]:
                if left.semantic_key != right.semantic_key or left.semantic_value == right.semantic_value or not _overlap(left, right):
                    continue
                ids = tuple(sorted((left.evidence_id, right.evidence_id)))
                found[(left.semantic_key, ids)] = EvidenceConflict(
                    code=f"{domain}_{left.semantic_key}_conflict"[:120],
                    domain=domain,
                    semantic_key=left.semantic_key,
                    evidence_ids=list(ids),
                    source_kinds=[left.source_kind, right.source_kind],
                )
        return list(found.values())

    def assess(self, *, relevant_domains: Iterable[str], evidence: Iterable[EvidenceItem]) -> EvidenceJudgeResult:
        domains = list(dict.fromkeys(relevant_domains))
        items = self.deduplicate(evidence)
        assessments: list[EvidenceAssessment] = []
        readiness: list[DomainReadiness] = []
        for domain in domains:
            profile = self.profiles.get(domain)
            if profile is None:
                assessment = EvidenceAssessment(domain=domain, status=EvidenceAssessmentStatus.NOT_APPLICABLE, limitations=["EVIDENCE_PROFILE_NOT_DEFINED"])
                assessments.append(assessment)
                readiness.append(DomainReadiness(domain=domain, readiness=DecisionReadiness.NOT_APPLICABLE, limitations=assessment.limitations))
                continue
            domain_items = [item for item in items if item.domain == domain]
            usable = [item for item in domain_items if item.usability != EvidenceUsability.UNUSABLE]
            missing: list[MissingEvidence] = []
            limited_required = False
            for requirement in profile.required:
                matches = [item for item in usable if item.fact_key in requirement.fact_keys and item.evidence_kind in requirement.accepted_kinds]
                if not matches:
                    missing.append(MissingEvidence(fact_keys=requirement.fact_keys, description=requirement.description, candidate_tools=requirement.candidate_tools, automatically_resolvable=bool(requirement.candidate_tools)))
                elif all(
                    item.usability == EvidenceUsability.LIMITED
                    or item.coverage != EvidenceCoverage.COMPLETE
                    or item.freshness == EvidenceFreshness.STALE
                    for item in matches
                ):
                    limited_required = True
            conflicts = self.conflicts(items, domain)
            if conflicts:
                status = EvidenceAssessmentStatus.CONFLICTED
            elif missing and not usable:
                status = EvidenceAssessmentStatus.MISSING
            elif missing or limited_required:
                status = EvidenceAssessmentStatus.PARTIAL
            else:
                status = EvidenceAssessmentStatus.SUFFICIENT
            limitations = list(dict.fromkeys(code for item in domain_items for code in item.limitation_codes))
            source_summary = dict(Counter(item.source_kind.value for item in usable))
            assessment = EvidenceAssessment(domain=domain, status=status, usable_evidence=[item.evidence_id for item in usable], missing_evidence=missing, conflicts=conflicts, limitations=limitations, source_summary=source_summary)
            assessments.append(assessment)
            mapped = {
                EvidenceAssessmentStatus.SUFFICIENT: DecisionReadiness.READY,
                EvidenceAssessmentStatus.PARTIAL: DecisionReadiness.PARTIAL,
                EvidenceAssessmentStatus.CONFLICTED: DecisionReadiness.PARTIAL,
                EvidenceAssessmentStatus.MISSING: DecisionReadiness.BLOCKED,
                EvidenceAssessmentStatus.NOT_APPLICABLE: DecisionReadiness.NOT_APPLICABLE,
            }[status]
            readiness.append(DomainReadiness(domain=domain, readiness=mapped, limitations=list(dict.fromkeys([*limitations, *[conflict.code for conflict in conflicts]]))))
        fingerprint = _stable_hash([(item.evidence_id, item.usability.value, item.coverage.value, item.semantic_value) for item in items if item.usability != EvidenceUsability.UNUSABLE])
        return EvidenceJudgeResult(relevant_domains=domains, evidence=items, assessments=assessments, decision_readiness=readiness, evidence_fingerprint=fingerprint)


_DOMAIN_TERMS: dict[str, tuple[str, ...]] = {
    "subjective_fatigue": ("主观疲劳", "rpe", "subjective fatigue", "自我感觉"),
    "recovery": ("恢复", "recovery", "hrv", "睡眠", "静息心率", "body battery"),
    "training_volume": ("跑量", "里程", "training volume", "distance"),
    "training_frequency": ("训练频率", "跑步次数", "training frequency"),
    "recent_intensity": ("训练强度", "近期强度", "intensity", "阈值", "间歇"),
    "training_load": ("训练负荷", "training load", "负荷状态"),
    "training_phase": ("训练阶段", "training phase", "周期阶段"),
}
_CERTAINTY_TERMS = (
    "可以确定",
    "能够确定",
    "明确",
    "一定",
    "肯定",
    "明显偏高",
    "显著偏高",
    "明显偏低",
    "显著偏低",
    "恢复很好",
    "恢复很差",
    "definitely",
    "certainly",
    "clearly",
)


def evidence_claim_violations(
    text: str,
    assessments: Iterable[EvidenceAssessment],
) -> list[str]:
    """Reject certainty that exceeds canonical evidence status.

    This intentionally checks bounded, high-risk phrases only.  It is not an
    NLP classifier and does not invent a probabilistic confidence score.
    """

    lowered = text.lower()
    certainty = any(term in lowered for term in _CERTAINTY_TERMS)
    if not certainty:
        return []
    violations: list[str] = []
    for assessment in assessments:
        terms = _DOMAIN_TERMS.get(assessment.domain, ())
        if not terms or not any(term in lowered for term in terms):
            continue
        if assessment.status == EvidenceAssessmentStatus.MISSING:
            violations.append(f"BLOCKED_DOMAIN_HALLUCINATION:{assessment.domain}")
        elif assessment.status == EvidenceAssessmentStatus.CONFLICTED:
            violations.append(f"CONFLICTED_DOMAIN_OVERCLAIM:{assessment.domain}")
        elif assessment.status == EvidenceAssessmentStatus.PARTIAL:
            violations.append(f"PARTIAL_EVIDENCE_CERTAINTY:{assessment.domain}")
    return violations
