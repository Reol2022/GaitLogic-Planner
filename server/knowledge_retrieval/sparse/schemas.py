from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from server.knowledge_retrieval.schemas import SHA256_PATTERN, StrictModel


class Bm25IndexManifest(StrictModel):
    schema_version: str = "1.0.0"
    index_id: str
    corpus_root_hash: str
    corpus_manifest_sha256: str
    strategy: str = "bm25_v1"
    analyzer_version: str
    k1: float = Field(gt=0)
    b: float = Field(ge=0, le=1)
    chunk_count: int = Field(ge=0)
    chunk_ids: list[str]
    chunk_content_hashes: dict[str, str]
    created_at: datetime
    root_hash: str

    @field_validator("corpus_root_hash", "corpus_manifest_sha256", "root_hash")
    @classmethod
    def valid_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("Index hashes must be lowercase SHA-256.")
        return value

    @model_validator(mode="after")
    def complete_chunk_references(self) -> "Bm25IndexManifest":
        if len(self.chunk_ids) != len(set(self.chunk_ids)):
            raise ValueError("BM25 index contains duplicate chunks.")
        if set(self.chunk_ids) != set(self.chunk_content_hashes):
            raise ValueError("BM25 index chunk hashes are incomplete.")
        if self.chunk_count != len(self.chunk_ids):
            raise ValueError("BM25 index chunk count is invalid.")
        return self


class Bm25IndexPayload(StrictModel):
    manifest: Bm25IndexManifest
    documents: list[dict[str, object]]
