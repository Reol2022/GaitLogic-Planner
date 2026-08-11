from __future__ import annotations

from datetime import datetime
import math
import re

from pydantic import Field, field_validator, model_validator

from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeDocumentStatus,
)
from server.knowledge_retrieval.schemas import (
    SHA256_PATTERN,
    StrictModel,
)


class VectorRecord(StrictModel):
    chunk_id: str
    document_id: str
    content_sha256: str
    vector: list[float]
    category: KnowledgeCategory
    tags: list[str]
    source_id: str
    knowledge_version: str
    language: str
    status: KnowledgeDocumentStatus
    section: str
    relative_path: str

    @field_validator("content_sha256")
    @classmethod
    def hash_is_valid(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("content_sha256 must be lowercase SHA-256.")
        return value

    @field_validator("vector")
    @classmethod
    def vector_is_valid(cls, value: list[float]) -> list[float]:
        if not value or not all(math.isfinite(float(item)) for item in value):
            raise ValueError("vector must contain finite values.")
        return [float(item) for item in value]

    @field_validator("relative_path")
    @classmethod
    def path_is_relative(cls, value: str) -> str:
        if (
            not value
            or value.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", value)
            or ".." in value.replace("\\", "/").split("/")
            or "\\" in value
        ):
            raise ValueError("relative_path must be a safe POSIX relative path.")
        return value


class VectorSearchResult(StrictModel):
    chunk_id: str
    score: float = Field(ge=-1, le=1)


class VectorStoreValidationResult(StrictModel):
    valid: bool
    record_count: int = Field(ge=0)
    dimensions: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class IndexManifest(StrictModel):
    schema_version: str
    index_id: str
    corpus_root_hash: str
    corpus_manifest_sha256: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int = Field(ge=1)
    embedding_normalized: bool
    vector_store: str
    distance_metric: str
    chunk_count: int = Field(ge=0)
    chunk_ids: list[str]
    chunk_content_hashes: dict[str, str]
    vector_hashes: dict[str, str]
    created_at: datetime
    root_hash: str
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "corpus_root_hash",
        "corpus_manifest_sha256",
        "root_hash",
    )
    @classmethod
    def hash_is_valid(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Manifest hashes must be lowercase SHA-256.")
        return value

    @model_validator(mode="after")
    def references_match(self) -> IndexManifest:
        ids = set(self.chunk_ids)
        if len(ids) != len(self.chunk_ids):
            raise ValueError("Index manifest contains duplicate chunk IDs.")
        if ids != set(self.chunk_content_hashes) or ids != set(self.vector_hashes):
            raise ValueError("Index manifest chunk references are incomplete.")
        if self.chunk_count != len(self.chunk_ids):
            raise ValueError("Index manifest chunk count is invalid.")
        return self


class IndexBuildPlan(StrictModel):
    provider: str
    model: str
    vector_store: str
    dimensions: int | None
    chunk_count: int = Field(ge=0)
    estimated_batches: int = Field(ge=0)
    corpus_root_hash: str
    index_root: str
    dry_run: bool = True


class IndexBuildResult(StrictModel):
    manifest: IndexManifest
    relative_path: str
    written: bool
    unchanged: bool


class IndexListItem(StrictModel):
    index_id: str
    corpus_root_hash: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    vector_store: str
    chunk_count: int
    root_hash: str
    created_at: datetime
