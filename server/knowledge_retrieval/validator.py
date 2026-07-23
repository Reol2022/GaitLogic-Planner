from __future__ import annotations

from collections import Counter
import re

from server.knowledge_retrieval.chunker import content_sha256
from server.knowledge_retrieval.errors import KnowledgeValidationError
from server.knowledge_retrieval.manifest import calculate_root_hash
from server.knowledge_retrieval.schemas import (
    CorpusManifest,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)


WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?:^|[\s`\"'])(?:[A-Z]:\\|\\\\)")
UNIX_ABSOLUTE_PATH = re.compile(r"(?:^|[\s`\"'])/(?:home|Users|var|tmp)/")
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+\S+"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|token)\s*[:=]\s*[\"']?(?!change-me|your_|<)[^\s\"']{8,}"),
)
PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _duplicates(values: list[str]) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def _validate_public_text(value: str, label: str) -> None:
    if WINDOWS_ABSOLUTE_PATH.search(value) or UNIX_ABSOLUTE_PATH.search(value):
        raise KnowledgeValidationError(f"{label}: absolute machine path is not allowed.")
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise KnowledgeValidationError(f"{label}: possible credential is not allowed.")
    if PHONE_PATTERN.search(value) or EMAIL_PATTERN.search(value):
        raise KnowledgeValidationError(f"{label}: possible user identity is not allowed.")


class KnowledgeCorpusValidator:
    def validate_loaded(
        self,
        documents: list[KnowledgeDocument],
        sources: list[KnowledgeSource],
        chunks: list[KnowledgeChunk],
    ) -> None:
        duplicate_documents = _duplicates(
            [item.metadata.document_id for item in documents]
        )
        duplicate_sources = _duplicates([item.source_id for item in sources])
        duplicate_chunks = _duplicates([item.chunk_id for item in chunks])
        if duplicate_documents:
            raise KnowledgeValidationError(
                f"Duplicate document IDs: {duplicate_documents}."
            )
        if duplicate_sources:
            raise KnowledgeValidationError(
                f"Duplicate source IDs: {duplicate_sources}."
            )
        if duplicate_chunks:
            raise KnowledgeValidationError(
                f"Duplicate chunk IDs: {duplicate_chunks}."
            )
        source_ids = {item.source_id for item in sources}
        document_ids = {item.metadata.document_id for item in documents}
        for source in sources:
            _validate_public_text(
                " ".join(
                    filter(
                        None,
                        [
                            source.title,
                            *source.authors,
                            source.notes,
                            source.url,
                        ],
                    )
                ),
                f"source {source.source_id}",
            )
        for document in documents:
            if document.metadata.source_id not in source_ids:
                raise KnowledgeValidationError(
                    f"{document.metadata.document_id}: source does not exist."
                )
            _validate_public_text(
                f"{document.metadata.title}\n{document.body}",
                f"document {document.metadata.document_id}",
            )
        chunks_by_document = Counter(item.document_id for item in chunks)
        for chunk in chunks:
            if chunk.document_id not in document_ids:
                raise KnowledgeValidationError(
                    f"{chunk.chunk_id}: document does not exist."
                )
            if chunk.source_id not in source_ids:
                raise KnowledgeValidationError(
                    f"{chunk.chunk_id}: source does not exist."
                )
            _validate_public_text(chunk.content, f"chunk {chunk.chunk_id}")
        for document in documents:
            if chunks_by_document[document.metadata.document_id] == 0:
                raise KnowledgeValidationError(
                    f"{document.metadata.document_id}: no chunks were generated."
                )

    def validate_manifest(self, manifest: CorpusManifest) -> None:
        document_ids = [item.document_id for item in manifest.documents]
        source_ids = [item.source_id for item in manifest.sources]
        chunk_ids = [item.chunk_id for item in manifest.chunks]
        if _duplicates(document_ids):
            raise KnowledgeValidationError("Manifest contains duplicate document IDs.")
        if _duplicates(source_ids):
            raise KnowledgeValidationError("Manifest contains duplicate source IDs.")
        if _duplicates(chunk_ids):
            raise KnowledgeValidationError("Manifest contains duplicate chunk IDs.")
        document_id_set = set(document_ids)
        source_id_set = set(source_ids)
        chunk_id_set = set(chunk_ids)
        chunks_by_document: dict[str, set[str]] = {}
        for chunk in manifest.chunks:
            if content_sha256(chunk.content) != chunk.content_sha256:
                raise KnowledgeValidationError(
                    f"Manifest chunk content hash is invalid: {chunk.chunk_id}."
                )
            if chunk.document_id not in document_id_set:
                raise KnowledgeValidationError(
                    f"Manifest chunk references missing document: {chunk.chunk_id}."
                )
            if chunk.source_id not in source_id_set:
                raise KnowledgeValidationError(
                    f"Manifest chunk references missing source: {chunk.chunk_id}."
                )
            chunks_by_document.setdefault(chunk.document_id, set()).add(
                chunk.chunk_id
            )
        for document in manifest.documents:
            if document.source_id not in source_id_set:
                raise KnowledgeValidationError(
                    f"Manifest document references missing source: {document.document_id}."
                )
            if set(document.chunk_ids) != chunks_by_document.get(
                document.document_id, set()
            ):
                raise KnowledgeValidationError(
                    f"Manifest chunk references are incomplete: {document.document_id}."
                )
            if not set(document.chunk_ids).issubset(chunk_id_set):
                raise KnowledgeValidationError(
                    f"Manifest contains unknown chunk IDs: {document.document_id}."
                )
        expected_root_hash = calculate_root_hash(
            manifest.documents,
            manifest.sources,
            manifest.chunks,
            schema_version=manifest.schema_version,
            chunker_version=manifest.chunker_version,
        )
        if expected_root_hash != manifest.root_hash:
            raise KnowledgeValidationError("Manifest root hash is invalid.")
        if manifest.statistics.document_count != len(manifest.documents):
            raise KnowledgeValidationError("Manifest document statistics are invalid.")
        if manifest.statistics.source_count != len(manifest.sources):
            raise KnowledgeValidationError("Manifest source statistics are invalid.")
        if manifest.statistics.chunk_count != len(manifest.chunks):
            raise KnowledgeValidationError("Manifest chunk statistics are invalid.")
