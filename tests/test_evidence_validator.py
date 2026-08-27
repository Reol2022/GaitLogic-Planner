from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.errors import AgentErrorCode
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext, AgentModelOutput
from server.agent.validator import AgentResponseValidator
from server.domain.evidence import EvidenceAssessment, EvidenceAssessmentStatus


def context(assessment: EvidenceAssessment) -> AgentContext:
    return AgentContext(
        request_id="5ef6ac0d-b831-455c-bdf5-664af0f59a50",
        user_id=7001,
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        current_time=datetime(2026, 8, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone="Asia/Shanghai",
        evidence_assessments=[assessment],
    )


@pytest.mark.parametrize(
    ("assessment", "answer"),
    [
        (
            EvidenceAssessment(
                domain="subjective_fatigue",
                status=EvidenceAssessmentStatus.MISSING,
            ),
            "可以确定你本周主观疲劳明显偏高。",
        ),
        (
            EvidenceAssessment(
                domain="recovery",
                status=EvidenceAssessmentStatus.CONFLICTED,
            ),
            "你的恢复状态明确很差。",
        ),
        (
            EvidenceAssessment(
                domain="training_volume",
                status=EvidenceAssessmentStatus.PARTIAL,
            ),
            "可以确定你的跑量明显偏高。",
        ),
    ],
)
def test_validator_rejects_claims_beyond_evidence_status(assessment, answer) -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer=answer,
        risk_level=AgentRiskLevel.UNKNOWN,
    )
    result = AgentResponseValidator().validate_model_output(
        output,
        context=context(assessment),
        registry=AgentToolRegistry(),
        final=True,
    )
    assert AgentErrorCode.AGENT_VALIDATION_FAILED in result.errors


def test_validator_allows_explicit_conflict_uncertainty() -> None:
    output = AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="主观感受与设备恢复信号不完全一致，暂不做确定判断。",
        risk_level=AgentRiskLevel.UNKNOWN,
    )
    result = AgentResponseValidator().validate_model_output(
        output,
        context=context(
            EvidenceAssessment(
                domain="recovery",
                status=EvidenceAssessmentStatus.CONFLICTED,
            )
        ),
        registry=AgentToolRegistry(),
        final=True,
    )
    assert result.valid
