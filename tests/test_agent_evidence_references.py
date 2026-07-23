from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.agent.enums import AgentIntent
from server.agent.providers.schemas import ProviderAgentModelOutput
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.today_recommendation import (
    build_evidence_catalog,
    materialize_evidence_references,
)
from tests.agent_tool_fakes import NOW


def evidence_context(*, with_evidence: bool = True) -> AgentContext:
    request = AgentRequest(
        user_id=501,
        message="fictional",
        intent=AgentIntent.TODAY_RECOMMENDATION,
    )
    evaluation = {
        "evidence": ["distance_7d_km", "distance_7d_km"],
        "rule_hits": [
            {
                "rule_code": "TODAY_PUBLIC_RULE",
                "explanation": "Existing rule evidence.",
            }
        ],
    }
    return AgentContext(
        request_id=request.request_id,
        user_id=request.user_id,
        intent=request.intent,
        current_time=NOW,
        timezone="Asia/Shanghai",
        today_evaluation=evaluation if with_evidence else {},
    )


def provider_payload(key_evidence_ids) -> dict:
    return {
        "answer": "Use the existing plan.",
        "intent": "TODAY_RECOMMENDATION",
        "today_recommendation": {
            "decision": "PROCEED",
            "planned_workout_status": "PLANNED",
            "headline": "Proceed.",
            "key_evidence_ids": key_evidence_ids,
            "data_quality": "AVAILABLE",
        },
    }


def test_catalog_is_stable_ordered_and_request_local() -> None:
    context = evidence_context()
    first = build_evidence_catalog(context)
    second = build_evidence_catalog(context)
    assert first == second
    assert [(item.id, item.text) for item in first] == [
        ("evidence_1", "distance_7d_km"),
        ("evidence_2", "TODAY_PUBLIC_RULE"),
        ("evidence_3", "Existing rule evidence."),
    ]
    serialized = repr(first)
    assert str(context.user_id) not in serialized
    assert ":\\" not in serialized
    assert "/" not in serialized


def test_materialization_uses_canonical_order_not_model_order() -> None:
    assert materialize_evidence_references(
        ["evidence_3", "evidence_1"],
        evidence_context(),
    ) == ["distance_7d_km", "Existing rule evidence."]


@pytest.mark.parametrize(
    "references",
    [
        ["evidence_99"],
        ["Evidence_1"],
        [" evidence_1"],
        ["evidence_1 "],
        ["distance_7d_km"],
        ["evidence_1", "evidence_1"],
        [],
    ],
)
def test_materialization_rejects_invalid_references(references: list[str]) -> None:
    with pytest.raises(ValueError):
        materialize_evidence_references(references, evidence_context())


def test_empty_references_are_allowed_only_without_canonical_evidence() -> None:
    assert materialize_evidence_references([], evidence_context(with_evidence=False)) == []


@pytest.mark.parametrize(
    "ids",
    [
        [1],
        [""],
        [" evidence_1"],
        ["evidence_1 "],
        ["Evidence_1"],
        ["evidence_01"],
        ["evidence_1", "evidence_1"],
    ],
)
def test_provider_schema_rejects_invalid_evidence_ids(ids) -> None:
    with pytest.raises(ValidationError):
        ProviderAgentModelOutput.model_validate(provider_payload(ids))


def test_provider_schema_requires_ids_and_rejects_legacy_text() -> None:
    missing = provider_payload(["evidence_1"])
    del missing["today_recommendation"]["key_evidence_ids"]
    legacy = provider_payload(["evidence_1"])
    legacy["today_recommendation"]["key_evidence"] = ["distance_7d_km"]
    with pytest.raises(ValidationError):
        ProviderAgentModelOutput.model_validate(missing)
    with pytest.raises(ValidationError):
        ProviderAgentModelOutput.model_validate(legacy)
