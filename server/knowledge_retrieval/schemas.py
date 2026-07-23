from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeDocumentStatus,
    KnowledgeEvidenceLevel,
    KnowledgeSourceType,
    LicenseStatus,
    SourceUsagePolicy,
)
from server.schemas.runner_state import TrainingPhaseState


SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeDocumentMetadata(StrictModel):
    document_id: str
    title: str = Field(min_length=1, max_length=200)
    category: KnowledgeCategory
    tags: list[str] = Field(default_factory=list, max_length=30)
    applicable_phases: list[TrainingPhaseState] = Field(default_factory=list)
    source_id: str
    source_type: KnowledgeSourceType
    evidence_level: KnowledgeEvidenceLevel
    knowledge_version: str
    language: str
    status: KnowledgeDocumentStatus
    reviewed_at: date | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    author: str | None = Field(default=None, max_length=120)
    license: str | None = Field(default=None, max_length=200)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("document_id", "source_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("ID must use stable lowercase kebab-case.")
        return value

    @field_validator("knowledge_version")
    @classmethod
    def validate_semver(cls, value: str) -> str:
        if not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("knowledge_version must use semantic versioning.")
        return value

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if not LANGUAGE_PATTERN.fullmatch(value):
            raise ValueError("language must use a controlled language tag such as zh-CN.")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            tag = value.strip().lower()
            if not ID_PATTERN.fullmatch(tag):
                raise ValueError("tags must use lowercase kebab-case.")
            if tag not in seen:
                normalized.append(tag)
                seen.add(tag)
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> KnowledgeDocumentMetadata:
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValueError("valid_from cannot be after valid_until.")
        return self


class KnowledgeSourceDefinition(StrictModel):
    source_id: str
    title: str = Field(min_length=1, max_length=300)
    source_type: KnowledgeSourceType
    authors: list[str] = Field(default_factory=list, max_length=20)
    edition: str | None = Field(default=None, max_length=120)
    publication_year: int | None = Field(default=None, ge=1800, le=2200)
    publisher: str | None = Field(default=None, max_length=200)
    license_status: LicenseStatus
    usage_policy: SourceUsagePolicy
    url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("source_id must use stable lowercase kebab-case.")
        return value


class KnowledgeSource(KnowledgeSourceDefinition):
    relative_path: str
    record_sha256: str

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if not value or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
            raise ValueError("relative_path cannot be absolute.")
        if ".." in value.replace("\\", "/").split("/"):
            raise ValueError("relative_path cannot traverse directories.")
        if "\\" in value:
            raise ValueError("relative_path must use forward slashes.")
        return value

    @field_validator("record_sha256")
    @classmethod
    def validate_record_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("record_sha256 must be lowercase SHA-256.")
        return value


class KnowledgeDocument(StrictModel):
    metadata: KnowledgeDocumentMetadata
    body: str
    relative_path: str
    file_sha256: str

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if not value or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
            raise ValueError("relative_path cannot be absolute.")
        if ".." in value.replace("\\", "/").split("/"):
            raise ValueError("relative_path cannot traverse directories.")
        if "\\" in value:
            raise ValueError("relative_path must use forward slashes.")
        return value

    @field_validator("file_sha256")
    @classmethod
    def validate_file_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("file_sha256 must be lowercase SHA-256.")
        return value


class ChunkMetadata(StrictModel):
    evidence_level: KnowledgeEvidenceLevel
    source_type: KnowledgeSourceType
    language: str
    status: KnowledgeDocumentStatus
    applicable_phases: list[TrainingPhaseState] = Field(default_factory=list)
    document_path: str


class KnowledgeChunk(StrictModel):
    chunk_id: str
    document_id: str
    title: str
    section: str
    section_path: list[str]
    category: KnowledgeCategory
    tags: list[str]
    source_id: str
    knowledge_version: str
    content: str
    content_sha256: str
    ordinal: int = Field(ge=1)
    char_count: int = Field(ge=1)
    estimated_token_count: int = Field(ge=1)
    metadata: ChunkMetadata

    @field_validator("content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("content_sha256 must be lowercase SHA-256.")
        return value


class ManifestDocumentRecord(StrictModel):
    document_id: str
    title: str
    relative_path: str
    file_sha256: str
    source_id: str
    knowledge_version: str
    status: KnowledgeDocumentStatus
    category: KnowledgeCategory
    tags: list[str]
    chunk_ids: list[str]


class ManifestSourceRecord(StrictModel):
    source_id: str
    title: str
    source_type: KnowledgeSourceType
    relative_path: str
    record_sha256: str


class CorpusStatistics(StrictModel):
    document_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    total_char_count: int = Field(ge=0)
    estimated_token_count: int = Field(ge=0)
    categories: dict[str, int] = Field(default_factory=dict)
    statuses: dict[str, int] = Field(default_factory=dict)


class CorpusManifest(StrictModel):
    schema_version: str
    corpus_version: str
    generator_version: str
    chunker_version: str
    documents: list[ManifestDocumentRecord]
    sources: list[ManifestSourceRecord]
    chunks: list[KnowledgeChunk]
    root_hash: str
    generated_at: datetime
    statistics: CorpusStatistics

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("schema_version must use semantic versioning.")
        return value

    @field_validator("root_hash")
    @classmethod
    def validate_root_hash(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("root_hash must be lowercase SHA-256.")
        return value


class CorpusBuildResult(StrictModel):
    manifest: CorpusManifest
    output_path: str
    written: bool
    unchanged: bool
    dry_run: bool


class CorpusListItem(StrictModel):
    document_id: str
    title: str
    category: KnowledgeCategory
    status: KnowledgeDocumentStatus
    knowledge_version: str
    source_id: str
    chunk_count: int
    file_sha256: str


def canonical_model_data(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)
