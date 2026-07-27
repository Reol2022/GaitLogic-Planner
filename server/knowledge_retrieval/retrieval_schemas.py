from __future__ import annotations

from pydantic import Field, field_validator

from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeEvidenceLevel,
)
from server.knowledge_retrieval.schemas import StrictModel


MAX_QUERY_CHARS = 4000
MAX_EXCERPT_CHARS = 600


class RetrievalFilters(StrictModel):
    categories: list[KnowledgeCategory] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=20)
    language: str | None = Field(default=None, min_length=2, max_length=20)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})


class KnowledgeRetrievalRequest(StrictModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    top_k: int = Field(default=4, ge=1, le=10)
    categories: list[KnowledgeCategory] = Field(default_factory=list, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=20)
    language: str | None = Field(default=None, min_length=2, max_length=20)
    min_score: float | None = Field(default=None, ge=-1, le=1)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be blank.")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})

    def filters(self) -> RetrievalFilters:
        return RetrievalFilters(
            categories=self.categories,
            tags=self.tags,
            language=self.language,
        )


class KnowledgeRetrievalResult(StrictModel):
    rank: int = Field(ge=1)
    score: float = Field(ge=-1, le=1)
    chunk_id: str
    document_id: str
    title: str
    section: str
    excerpt: str = Field(max_length=MAX_EXCERPT_CHARS)
    category: KnowledgeCategory
    tags: list[str]
    source_id: str
    source_title: str
    knowledge_version: str
    evidence_level: KnowledgeEvidenceLevel
    relative_path: str
    limitations: list[str] = Field(default_factory=list)


class KnowledgeRetrievalResponse(StrictModel):
    query: str
    results: list[KnowledgeRetrievalResult]
    limitations: list[str] = Field(default_factory=list)
    index_id: str
    corpus_root_hash: str
