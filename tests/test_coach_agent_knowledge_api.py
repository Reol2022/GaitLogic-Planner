from __future__ import annotations

import json

from server.agent.enums import AgentIntent, AgentRiskLevel
from server.main import app
from server.schemas.coach_agent import CoachQueryResponse
from tests.agent_tool_fakes import NOW


def test_public_response_is_backward_compatible_with_empty_references() -> None:
    response = CoachQueryResponse(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        trace_id="64ce7fe5-32d2-48cc-9bc0-6c61d2f25c25",
        status="SUCCEEDED",
        intent=AgentIntent.GENERAL_TRAINING_QUESTION,
        answer="Safe fictional answer.",
        risk_level=AgentRiskLevel.UNKNOWN,
        provider_status="SUCCEEDED",
        generated_at=NOW,
    )
    assert response.knowledge_references == []


def test_openapi_exposes_only_canonical_public_knowledge_fields() -> None:
    schema = app.openapi()
    response_schema = schema["components"]["schemas"]["CoachKnowledgeReferenceRead"]
    assert set(response_schema["properties"]) == {
        "document_id",
        "title",
        "section",
        "source_id",
        "source_title",
        "knowledge_version",
        "evidence_level",
        "excerpt",
        "limitations",
    }
    serialized = json.dumps(schema, ensure_ascii=False)
    assert "knowledge_reference_id" not in serialized
    assert "ProviderTodayModelOutput" not in serialized
    assert "ProviderAgentModelOutput" not in serialized
