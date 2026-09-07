from server.domain.evidence import EvidenceAssessment, EvidenceAssessmentStatus, EvidenceJudgeResult
from server.observability.decision import DecisionOutcome, classify_decision_outcome


def _result(*statuses: EvidenceAssessmentStatus) -> EvidenceJudgeResult:
    return EvidenceJudgeResult.model_construct(
        assessments=[EvidenceAssessment.model_construct(domain=str(index), status=status) for index, status in enumerate(statuses)]
    )


def test_decision_outcome_is_read_only_assessment_classification() -> None:
    assert classify_decision_outcome(_result(EvidenceAssessmentStatus.SUFFICIENT)) == DecisionOutcome.FULL_ANSWER
    assert classify_decision_outcome(_result(EvidenceAssessmentStatus.PARTIAL, EvidenceAssessmentStatus.SUFFICIENT)) == DecisionOutcome.PARTIAL_ANSWER
    assert classify_decision_outcome(_result(EvidenceAssessmentStatus.MISSING)) == DecisionOutcome.GLOBAL_BLOCK


def test_not_applicable_domains_do_not_create_global_block() -> None:
    assert classify_decision_outcome(_result(EvidenceAssessmentStatus.NOT_APPLICABLE)) == DecisionOutcome.FULL_ANSWER
