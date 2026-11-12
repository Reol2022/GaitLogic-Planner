from __future__ import annotations

from datetime import date
import pytest

from server.domain.decision_readiness import DecisionReadiness
from server.domain.evidence import (
    EvidenceAssessmentStatus,
    EvidenceCoverage,
    EvidenceFreshness,
    EvidenceItem,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceSourceKind,
    EvidenceUsability,
)
from server.services.evidence_judge_service import EvidenceJudge, evidence_claim_violations
from server.domain.evidence import EvidenceAssessment


def item(
    evidence_id: str,
    *,
    domain: str = "training_volume",
    fact_key: str = "recent_training",
    kind: EvidenceKind = EvidenceKind.DERIVED_FACT,
    source: EvidenceSourceKind = EvidenceSourceKind.TRAINING_LOG,
    identity: str | None = None,
    coverage: EvidenceCoverage = EvidenceCoverage.COMPLETE,
    usability: EvidenceUsability = EvidenceUsability.USABLE,
    freshness: EvidenceFreshness = EvidenceFreshness.RECENT,
    semantic_key: str | None = None,
    semantic_value: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        evidence_kind=kind,
        source_kind=source,
        source_ref=f"source:{evidence_id}",
        domain=domain,
        fact_key=fact_key,
        semantic_key=semantic_key,
        semantic_value=semantic_value,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        freshness=freshness,
        coverage=coverage,
        usability=usability,
        provenance=EvidenceProvenance(
            canonical_fact_identity=identity or evidence_id,
            source_record_refs=[f"record:{evidence_id}"],
        ),
    )


def assessment(result, domain: str):
    return next(value for value in result.assessments if value.domain == domain)


def test_sufficient_evidence_maps_to_ready() -> None:
    result = EvidenceJudge().assess(
        relevant_domains=["training_volume"],
        evidence=[item("ev_volume")],
    )
    assert assessment(result, "training_volume").status == EvidenceAssessmentStatus.SUFFICIENT
    assert result.decision_readiness[0].readiness == DecisionReadiness.READY


def test_partial_coverage_and_stale_evidence_are_not_ready() -> None:
    for evidence in (
        item("ev_partial", coverage=EvidenceCoverage.PARTIAL),
        item("ev_stale", freshness=EvidenceFreshness.STALE),
    ):
        result = EvidenceJudge().assess(
            relevant_domains=["training_volume"], evidence=[evidence]
        )
        assert assessment(result, "training_volume").status == EvidenceAssessmentStatus.PARTIAL
        assert result.decision_readiness[0].readiness == DecisionReadiness.PARTIAL


def test_missing_required_evidence_maps_to_blocked() -> None:
    result = EvidenceJudge().assess(
        relevant_domains=["subjective_fatigue"], evidence=[]
    )
    value = assessment(result, "subjective_fatigue")
    assert value.status == EvidenceAssessmentStatus.MISSING
    assert value.missing_evidence[0].fact_keys == ["subjective_feedback"]
    assert result.decision_readiness[0].readiness == DecisionReadiness.BLOCKED


def test_duplicate_materializations_use_stable_canonical_identity() -> None:
    first = item("ev_first", identity="workout-log:7d")
    second = item("ev_second", identity="workout-log:7d")
    result = EvidenceJudge().assess(
        relevant_domains=["training_volume"], evidence=[first, second]
    )
    assert len(result.evidence) == 1
    assert len(assessment(result, "training_volume").usable_evidence) == 1


def test_conflicting_sources_do_not_choose_a_winner() -> None:
    subjective = item(
        "ev_subjective",
        domain="recovery",
        fact_key="recovery_signal",
        kind=EvidenceKind.PERSONAL_FACT,
        source=EvidenceSourceKind.USER_INPUT,
        semantic_key="recovery_signal",
        semantic_value="GOOD",
    )
    device = item(
        "ev_device",
        domain="recovery",
        fact_key="recovery_signal",
        kind=EvidenceKind.PERSONAL_FACT,
        source=EvidenceSourceKind.GARMIN_NORMALIZED,
        semantic_key="recovery_signal",
        semantic_value="WEAK",
    )
    result = EvidenceJudge().assess(
        relevant_domains=["recovery"], evidence=[subjective, device]
    )
    value = assessment(result, "recovery")
    assert value.status == EvidenceAssessmentStatus.CONFLICTED
    assert set(value.conflicts[0].source_kinds) == {
        EvidenceSourceKind.USER_INPUT,
        EvidenceSourceKind.GARMIN_NORMALIZED,
    }
    assert result.decision_readiness[0].readiness == DecisionReadiness.PARTIAL


def test_knowledge_and_capability_information_cannot_prove_user_recovery() -> None:
    knowledge = item(
        "ev_knowledge",
        domain="recovery",
        fact_key="knowledge_reference",
        kind=EvidenceKind.KNOWLEDGE_EVIDENCE,
        source=EvidenceSourceKind.KNOWLEDGE_CORPUS,
    )
    capability = item(
        "ev_capability",
        domain="recovery",
        fact_key="capability_information",
        kind=EvidenceKind.CAPABILITY_INFORMATION,
        source=EvidenceSourceKind.SYSTEM_CAPABILITY,
    )
    result = EvidenceJudge().assess(
        relevant_domains=["recovery"], evidence=[knowledge, capability]
    )
    assert assessment(result, "recovery").status == EvidenceAssessmentStatus.PARTIAL
    assert result.decision_readiness[0].readiness == DecisionReadiness.PARTIAL


def test_provenance_survives_assessment() -> None:
    evidence = item("ev_provenance")
    result = EvidenceJudge().assess(
        relevant_domains=["training_volume"], evidence=[evidence]
    )
    assert result.evidence[0].provenance.source_record_refs == ["record:ev_provenance"]


def test_irrelevant_missing_domain_does_not_affect_volume_question() -> None:
    result = EvidenceJudge().assess(
        relevant_domains=["training_volume"], evidence=[item("ev_volume_only")]
    )
    assert [value.domain for value in result.assessments] == ["training_volume"]
    assert result.decision_readiness[0].readiness == DecisionReadiness.READY


@pytest.mark.parametrize('text', [
    '本周跑量变化明确。恢复数据不足，暂不判断恢复状态。',
    '无法确定恢复状态。',
    '不能明确判断睡眠是否足够。',
    '恢复数据不足，不能据此确定恢复很好。',
    'Cannot definitely conclude recovery is adequate.',
])
def test_limited_recovery_is_not_contaminated_by_unrelated_certainty(text):
    values = [EvidenceAssessment(domain='recovery', status=EvidenceAssessmentStatus.PARTIAL)]
    assert evidence_claim_violations(text, values) == []


@pytest.mark.parametrize('status', [EvidenceAssessmentStatus.MISSING, EvidenceAssessmentStatus.PARTIAL, EvidenceAssessmentStatus.CONFLICTED])
@pytest.mark.parametrize('text', [
    '可以确定你恢复很好。',
    '睡眠肯定充足。',
    '无法确定训练阶段，但恢复肯定很好。',
    'Recovery is definitely adequate.',
])
def test_real_unsupported_recovery_certainty_remains_rejected(status, text):
    values = [EvidenceAssessment(domain='recovery', status=status)]
    assert evidence_claim_violations(text, values)
