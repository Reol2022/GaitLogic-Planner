from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from planner_core.config import Settings
from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext
from server.agent.tools.knowledge_tools import (
    RetrieveTrainingKnowledgeInput,
    RetrieveTrainingKnowledgeTool,
)
from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeEvidenceLevel,
)
from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.retrieval_schemas import (
    KnowledgeRetrievalResponse,
    KnowledgeRetrievalResult,
)
from tests.agent_tool_fakes import NOW
from tests.knowledge_index_helpers import build_test_index


def context(intent: AgentIntent = AgentIntent.GENERAL_TRAINING_QUESTION) -> AgentContext:
    return AgentContext(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        user_id=4101,
        intent=intent,
        current_time=NOW,
        timezone="Asia/Shanghai",
    )


class FakeRetriever:
    def __init__(self, *, empty: bool = False, error: Exception | None = None) -> None:
        self.empty = empty
        self.error = error
        self.requests = []

    def retrieve(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        results = [] if self.empty else [
            KnowledgeRetrievalResult(
                rank=1,
                score=0.82,
                chunk_id="recovery#principles#001",
                document_id="recovery-principles",
                title="恢复训练原则",
                section="核心原则",
                excerpt="疲劳较高时应优先保留训练连续性，并降低单次训练压力。",
                category=KnowledgeCategory.RECOVERY,
                tags=["fatigue", "recovery"],
                source_id="fictional-training-guidance",
                source_title="Fictional Training Guidance",
                knowledge_version="1.0.0",
                evidence_level=KnowledgeEvidenceLevel.SECONDARY,
                relative_path="documents/recovery/recovery-principles.md",
                limitations=[],
            )
        ]
        return KnowledgeRetrievalResponse(
            query=request.query,
            results=results,
            limitations=["No matching result."] if self.empty else [],
            index_id="knowledge-1234567890abcdef12345678",
            corpus_root_hash="a" * 64,
        )


def tool(retriever: FakeRetriever, *, maximum_top_k: int = 4):
    return RetrieveTrainingKnowledgeTool(
        lambda: retriever,
        maximum_top_k=maximum_top_k,
    )


def test_tool_schema_is_strict_bounded_and_read_only() -> None:
    definition = tool(FakeRetriever()).definition
    assert definition.read_only is True
    assert definition.requires_confirmation is False
    assert set(definition.allowed_intents) == {
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.EXPLAIN_RUNNER_STATE,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    }
    assert definition.input_schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        RetrieveTrainingKnowledgeInput(
            query="safe",
            user_id=9,
        )
    with pytest.raises(ValidationError):
        RetrieveTrainingKnowledgeInput(query=" ")
    with pytest.raises(ValidationError):
        RetrieveTrainingKnowledgeInput(query="safe", top_k=7)
    with pytest.raises(ValidationError):
        RetrieveTrainingKnowledgeInput(query="safe", language="fr-FR")
    with pytest.raises(ValidationError):
        RetrieveTrainingKnowledgeInput(query="safe", tags=["NOT VALID"])


def test_agent_knowledge_configuration_is_disabled_and_bounded_by_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.coach_agent_knowledge_retrieval_enabled is False
    assert settings.coach_agent_knowledge_index_id == ""
    assert settings.coach_agent_knowledge_top_k == 4
    with pytest.raises(ValidationError):
        Settings(_env_file=None, COACH_AGENT_KNOWLEDGE_TOP_K=7)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, COACH_AGENT_KNOWLEDGE_INDEX_ID="../private-index")


def test_tool_maps_ranked_canonical_results_and_filters() -> None:
    retriever = FakeRetriever()
    result = tool(retriever, maximum_top_k=3).execute(
        RetrieveTrainingKnowledgeInput(
            query="  疲劳较高时如何调整训练？  ",
            top_k=6,
            categories=[KnowledgeCategory.RECOVERY],
            tags=["Fatigue"],
        ),
        context(),
    )
    assert result.query_status == "SUCCEEDED"
    assert result.results[0].knowledge_reference_id == "knowledge_1"
    assert result.results[0].excerpt.startswith("疲劳较高")
    assert retriever.requests[0].query == "疲劳较高时如何调整训练？"
    assert retriever.requests[0].top_k == 3
    assert retriever.requests[0].categories == [KnowledgeCategory.RECOVERY]
    assert retriever.requests[0].tags == ["fatigue"]
    payload = result.model_dump(mode="json")
    assert "vector" not in str(payload)
    assert "relative_path" not in str(payload)


def test_empty_result_is_structured_and_does_not_invent_reference() -> None:
    result = tool(FakeRetriever(empty=True)).execute(
        RetrieveTrainingKnowledgeInput(query="无匹配知识"),
        context(),
    )
    assert result.query_status == "EMPTY"
    assert result.results == []
    assert result.limitations == ["No matching result."]


def test_registry_failure_is_safe_and_query_is_not_logged(caplog) -> None:
    query = "private fictional query that must not be logged"
    registry = AgentToolRegistry()
    registry.register(tool(FakeRetriever(error=RuntimeError("private failure"))))
    with caplog.at_level(logging.DEBUG):
        result = registry.invoke(
            "retrieve_training_knowledge",
            {"query": query},
            context(),
        )
    assert result.status == AgentToolStatus.FAILED
    assert result.data is None
    assert query not in caplog.text
    assert "private failure" not in caplog.text


def test_tool_is_not_allowed_for_weekly_review() -> None:
    registry = AgentToolRegistry()
    registry.register(tool(FakeRetriever()))
    result = registry.invoke(
        "retrieve_training_knowledge",
        {"query": "训练理论"},
        context(AgentIntent.WEEKLY_REVIEW),
    )
    assert result.status == AgentToolStatus.NOT_ALLOWED


def test_tool_integrates_with_deterministic_index_without_network_or_database(
    tmp_path,
) -> None:
    service, index_id = build_test_index(tmp_path, dimensions=32)
    knowledge_tool = RetrieveTrainingKnowledgeTool(
        lambda: TrainingKnowledgeRetriever(
            index_service=service,
            provider=DeterministicEmbeddingProvider(dimensions=32),
            index_id=index_id,
        )
    )
    result = knowledge_tool.execute(
        RetrieveTrainingKnowledgeInput(
            query="疲劳较高时如何安排恢复训练？",
            categories=[KnowledgeCategory.RECOVERY],
            top_k=4,
        ),
        context(),
    )
    assert result.query_status == "SUCCEEDED"
    assert result.results
    assert all(item.category == KnowledgeCategory.RECOVERY for item in result.results)
    assert [item.knowledge_reference_id for item in result.results] == [
        f"knowledge_{index}" for index in range(1, len(result.results) + 1)
    ]


def test_missing_index_fails_through_safe_registry_boundary(tmp_path) -> None:
    service, _index_id = build_test_index(tmp_path, dimensions=32)
    registry = AgentToolRegistry()
    registry.register(
        RetrieveTrainingKnowledgeTool(
            lambda: TrainingKnowledgeRetriever(
                index_service=service,
                provider=DeterministicEmbeddingProvider(dimensions=32),
                index_id="knowledge-ffffffffffffffffffffffff",
            )
        )
    )
    result = registry.invoke(
        "retrieve_training_knowledge",
        {"query": "恢复训练"},
        context(),
    )
    assert result.status == AgentToolStatus.FAILED
    assert result.data is None
