"""Read-only classification of existing Evidence Judge results for telemetry."""

from __future__ import annotations

from enum import StrEnum

from server.domain.evidence import EvidenceAssessmentStatus, EvidenceJudgeResult


class DecisionOutcome(StrEnum):
    """Stable observation only; it never drives a business decision."""

    FULL_ANSWER = "full_answer"
    PARTIAL_ANSWER = "partial_answer"
    GLOBAL_BLOCK = "global_block"


def classify_decision_outcome(result: EvidenceJudgeResult | None) -> DecisionOutcome | None:
    """Classify current assessments without inferring offline false blocks."""

    if result is None:
        return None
    applicable = [item.status for item in result.assessments if item.status != EvidenceAssessmentStatus.NOT_APPLICABLE]
    if not applicable:
        return DecisionOutcome.FULL_ANSWER
    if all(status == EvidenceAssessmentStatus.MISSING for status in applicable):
        return DecisionOutcome.GLOBAL_BLOCK
    if any(status != EvidenceAssessmentStatus.SUFFICIENT for status in applicable):
        return DecisionOutcome.PARTIAL_ANSWER
    return DecisionOutcome.FULL_ANSWER
