from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from planner_core.config import Settings
from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentContractModel
from server.agent.tool import AgentTool
from server.knowledge_retrieval.embeddings.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
)
from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeEvidenceLevel,
)
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.retrieval_schemas import (
    MAX_QUERY_CHARS,
    KnowledgeRetrievalRequest,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.schemas import ID_PATTERN


class RetrieveTrainingKnowledgeInput(AgentContractModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(default=4, ge=1, le=6)
    categories: list[KnowledgeCategory] = Field(default_factory=list, max_length=6)
    tags: list[str] = Field(default_factory=list, max_length=10)
    language: Literal["zh-CN", "en-US"] = "zh-CN"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be blank")
        return normalized

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tag_types(cls, value: object) -> object:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("tags must contain only strings")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            tag = value.strip().lower()
            if not tag or len(tag) > 40 or not ID_PATTERN.fullmatch(tag):
                raise ValueError("tags must use bounded lowercase kebab-case")
            if tag not in seen:
                normalized.append(tag)
                seen.add(tag)
        return normalized


class KnowledgeToolResultItem(AgentContractModel):
    knowledge_reference_id: str = Field(
        pattern=r"^knowledge_[1-9][0-9]*$",
        max_length=32,
    )
    chunk_id: str = Field(min_length=1, max_length=300)
    document_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    section: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(min_length=1, max_length=600)
    category: KnowledgeCategory
    source_id: str = Field(min_length=1, max_length=160)
    source_title: str = Field(min_length=1, max_length=300)
    knowledge_version: str = Field(min_length=1, max_length=80)
    evidence_level: KnowledgeEvidenceLevel
    score: float = Field(ge=-1, le=1)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class RetrieveTrainingKnowledgeOutput(AgentContractModel):
    query_status: Literal["SUCCEEDED", "EMPTY"]
    index_id: str = Field(min_length=1, max_length=80)
    corpus_root_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    results: list[KnowledgeToolResultItem] = Field(default_factory=list, max_length=6)
    limitations: list[str] = Field(default_factory=list, max_length=20)


KnowledgeRetrieverFactory = Callable[[], TrainingKnowledgeRetriever]


class RetrieveTrainingKnowledgeTool(AgentTool):
    name = "retrieve_training_knowledge"
    description = (
        "Retrieve bounded training-theory excerpts from the versioned knowledge "
        "index. It cannot read runner data or change a training decision."
    )
    input_model = RetrieveTrainingKnowledgeInput
    output_model = RetrieveTrainingKnowledgeOutput
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.EXPLAIN_RUNNER_STATE,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    )

    def __init__(
        self,
        retriever_factory: KnowledgeRetrieverFactory,
        *,
        maximum_top_k: int = 4,
    ) -> None:
        self.retriever_factory = retriever_factory
        self.maximum_top_k = maximum_top_k

    def execute(
        self,
        arguments: RetrieveTrainingKnowledgeInput,
        context: AgentContext,
    ) -> RetrieveTrainingKnowledgeOutput:
        del context
        retriever = self.retriever_factory()
        response = retriever.retrieve(
            KnowledgeRetrievalRequest(
                query=arguments.query,
                top_k=min(arguments.top_k, self.maximum_top_k),
                categories=arguments.categories,
                tags=arguments.tags,
                language=arguments.language,
            )
        )
        results = [
            KnowledgeToolResultItem(
                knowledge_reference_id=f"knowledge_{rank}",
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                title=item.title,
                section=item.section,
                excerpt=item.excerpt,
                category=item.category,
                source_id=item.source_id,
                source_title=item.source_title,
                knowledge_version=item.knowledge_version,
                evidence_level=item.evidence_level,
                score=item.score,
                limitations=item.limitations,
            )
            for rank, item in enumerate(response.results, start=1)
        ]
        return RetrieveTrainingKnowledgeOutput(
            query_status="SUCCEEDED" if results else "EMPTY",
            index_id=response.index_id,
            corpus_root_hash=response.corpus_root_hash,
            results=results,
            limitations=response.limitations,
        )


def build_configured_knowledge_tool(
    settings: Settings,
) -> RetrieveTrainingKnowledgeTool | None:
    if not settings.coach_agent_knowledge_retrieval_enabled:
        return None

    def factory() -> TrainingKnowledgeRetriever:
        if not settings.coach_agent_knowledge_index_id:
            raise ValueError("Coach knowledge index ID is not configured")
        service = KnowledgeIndexService(
            index_root=Path(settings.knowledge_index_runtime_directory)
        )
        provider = OpenAICompatibleEmbeddingProvider(settings)
        return TrainingKnowledgeRetriever(
            index_service=service,
            provider=provider,
            index_id=settings.coach_agent_knowledge_index_id,
        )

    return RetrieveTrainingKnowledgeTool(
        factory,
        maximum_top_k=settings.coach_agent_knowledge_top_k,
    )
