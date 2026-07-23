from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from server.knowledge_retrieval.chunker import CHUNKER_VERSION
from server.knowledge_retrieval.errors import KnowledgeBuildError
from server.knowledge_retrieval.schemas import (
    CorpusManifest,
    CorpusStatistics,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
    ManifestDocumentRecord,
    ManifestSourceRecord,
)


CORPUS_SCHEMA_VERSION = "1.0.0"
CORPUS_VERSION = "training-knowledge-1"
GENERATOR_VERSION = "knowledge-corpus-generator-1.0.0"


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def root_hash_payload(
    documents: list[ManifestDocumentRecord],
    sources: list[ManifestSourceRecord],
    chunks: list[KnowledgeChunk],
    *,
    schema_version: str = CORPUS_SCHEMA_VERSION,
    chunker_version: str = CHUNKER_VERSION,
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "chunker_version": chunker_version,
        "documents": [
            {
                "document_id": item.document_id,
                "file_sha256": item.file_sha256,
            }
            for item in sorted(documents, key=lambda record: record.document_id)
        ],
        "sources": [
            {
                "source_id": item.source_id,
                "record_sha256": item.record_sha256,
            }
            for item in sorted(sources, key=lambda record: record.source_id)
        ],
        "chunks": [
            {
                "chunk_id": item.chunk_id,
                "content_sha256": item.content_sha256,
            }
            for item in sorted(chunks, key=lambda record: record.chunk_id)
        ],
    }


def calculate_root_hash(
    documents: list[ManifestDocumentRecord],
    sources: list[ManifestSourceRecord],
    chunks: list[KnowledgeChunk],
    *,
    schema_version: str = CORPUS_SCHEMA_VERSION,
    chunker_version: str = CHUNKER_VERSION,
) -> str:
    return sha256_json(
        root_hash_payload(
            documents,
            sources,
            chunks,
            schema_version=schema_version,
            chunker_version=chunker_version,
        )
    )


def build_manifest(
    documents: list[KnowledgeDocument],
    sources: list[KnowledgeSource],
    chunks: list[KnowledgeChunk],
    *,
    generated_at: datetime | None = None,
) -> CorpusManifest:
    chunk_ids_by_document: dict[str, list[str]] = {}
    for chunk in chunks:
        chunk_ids_by_document.setdefault(chunk.document_id, []).append(chunk.chunk_id)
    document_records = [
        ManifestDocumentRecord(
            document_id=document.metadata.document_id,
            title=document.metadata.title,
            relative_path=document.relative_path,
            file_sha256=document.file_sha256,
            source_id=document.metadata.source_id,
            knowledge_version=document.metadata.knowledge_version,
            status=document.metadata.status,
            category=document.metadata.category,
            tags=document.metadata.tags,
            chunk_ids=sorted(
                chunk_ids_by_document.get(document.metadata.document_id, [])
            ),
        )
        for document in sorted(
            documents, key=lambda item: item.metadata.document_id
        )
    ]
    source_records = [
        ManifestSourceRecord(
            source_id=source.source_id,
            title=source.title,
            source_type=source.source_type,
            relative_path=source.relative_path,
            record_sha256=source.record_sha256,
        )
        for source in sorted(sources, key=lambda item: item.source_id)
    ]
    sorted_chunks = sorted(chunks, key=lambda item: item.chunk_id)
    category_counts = Counter(item.category.value for item in document_records)
    status_counts = Counter(item.status.value for item in document_records)
    return CorpusManifest(
        schema_version=CORPUS_SCHEMA_VERSION,
        corpus_version=CORPUS_VERSION,
        generator_version=GENERATOR_VERSION,
        chunker_version=CHUNKER_VERSION,
        documents=document_records,
        sources=source_records,
        chunks=sorted_chunks,
        root_hash=calculate_root_hash(
            document_records,
            source_records,
            sorted_chunks,
        ),
        generated_at=generated_at or datetime.now(timezone.utc),
        statistics=CorpusStatistics(
            document_count=len(document_records),
            source_count=len(source_records),
            chunk_count=len(sorted_chunks),
            total_char_count=sum(item.char_count for item in sorted_chunks),
            estimated_token_count=sum(
                item.estimated_token_count for item in sorted_chunks
            ),
            categories=dict(sorted(category_counts.items())),
            statuses=dict(sorted(status_counts.items())),
        ),
    )


def load_manifest(path: Path) -> CorpusManifest:
    try:
        return CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise KnowledgeBuildError("Existing corpus manifest is invalid.") from exc


def write_manifest_atomic(path: Path, manifest: CorpusManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    payload = (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise KnowledgeBuildError("Failed to publish corpus manifest atomically.") from exc
