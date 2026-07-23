from __future__ import annotations

from pathlib import Path
from typing import Any

from server.knowledge_retrieval.chunker import DeterministicKnowledgeChunker
from server.knowledge_retrieval.enums import KnowledgeDocumentStatus
from server.knowledge_retrieval.errors import (
    KnowledgeBuildError,
    KnowledgeNotFoundError,
    KnowledgeValidationError,
)
from server.knowledge_retrieval.loader import KnowledgeCorpusLoader
from server.knowledge_retrieval.manifest import (
    build_manifest,
    load_manifest,
    write_manifest_atomic,
)
from server.knowledge_retrieval.paths import CorpusPaths, safe_output_path
from server.knowledge_retrieval.schemas import (
    CorpusBuildResult,
    CorpusListItem,
    CorpusManifest,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)
from server.knowledge_retrieval.validator import KnowledgeCorpusValidator


DEFAULT_MANIFEST_PATH = Path("knowledge/manifests/corpus-v1.json")


class KnowledgeCorpusService:
    def __init__(
        self,
        knowledge_root: Path = Path("knowledge"),
        *,
        repository_root: Path | None = None,
        output_path: Path = DEFAULT_MANIFEST_PATH,
        chunker: DeterministicKnowledgeChunker | None = None,
    ) -> None:
        repository = (repository_root or Path.cwd()).resolve()
        resolved_knowledge = (
            knowledge_root.resolve()
            if knowledge_root.is_absolute()
            else (repository / knowledge_root).resolve()
        )
        self.paths = CorpusPaths.create(
            resolved_knowledge,
            repository_root=repository,
        )
        self.output_path = safe_output_path(output_path, repository)
        try:
            self.output_path.relative_to(self.paths.manifests_dir.resolve())
        except ValueError as exc:
            raise KnowledgeBuildError(
                "Manifest output must be inside knowledge/manifests."
            ) from exc
        self.loader = KnowledgeCorpusLoader(self.paths)
        self.chunker = chunker or DeterministicKnowledgeChunker()
        self.validator = KnowledgeCorpusValidator()

    @staticmethod
    def _filter_documents(
        documents: list[KnowledgeDocument],
        *,
        include_draft: bool,
        include_deprecated: bool,
    ) -> list[KnowledgeDocument]:
        included = {KnowledgeDocumentStatus.ACTIVE}
        if include_draft:
            included.add(KnowledgeDocumentStatus.DRAFT)
        if include_deprecated:
            included.add(KnowledgeDocumentStatus.DEPRECATED)
        return [
            document
            for document in documents
            if document.metadata.status in included
        ]

    def _current_corpus(
        self,
        *,
        include_draft: bool = False,
        include_deprecated: bool = False,
    ) -> tuple[list[KnowledgeDocument], list[KnowledgeSource], list[KnowledgeChunk]]:
        all_documents, sources = self.loader.load()
        documents = self._filter_documents(
            all_documents,
            include_draft=include_draft,
            include_deprecated=include_deprecated,
        )
        chunks = self.chunker.chunk_documents(documents)
        self.validator.validate_loaded(documents, sources, chunks)
        return documents, sources, chunks

    def validate(self) -> CorpusManifest:
        documents, sources, chunks = self._current_corpus()
        manifest = build_manifest(documents, sources, chunks)
        self.validator.validate_manifest(manifest)
        if self.output_path.exists():
            existing = load_manifest(self.output_path)
            self.validator.validate_manifest(existing)
            if existing.root_hash != manifest.root_hash:
                raise KnowledgeValidationError(
                    "Existing corpus manifest is stale; rebuild it after reviewing "
                    "the corpus changes."
                )
        return manifest

    def build(
        self,
        *,
        dry_run: bool = False,
        force: bool = False,
        include_draft: bool = False,
        include_deprecated: bool = False,
    ) -> CorpusBuildResult:
        documents, sources, chunks = self._current_corpus(
            include_draft=include_draft,
            include_deprecated=include_deprecated,
        )
        manifest = build_manifest(documents, sources, chunks)
        self.validator.validate_manifest(manifest)
        relative_output = self.output_path.relative_to(
            self.paths.repository_root
        ).as_posix()
        if dry_run:
            return CorpusBuildResult(
                manifest=manifest,
                output_path=relative_output,
                written=False,
                unchanged=False,
                dry_run=True,
            )
        if self.output_path.exists():
            existing = load_manifest(self.output_path)
            self.validator.validate_manifest(existing)
            if existing.root_hash == manifest.root_hash:
                return CorpusBuildResult(
                    manifest=existing,
                    output_path=relative_output,
                    written=False,
                    unchanged=True,
                    dry_run=False,
                )
            if not force:
                raise KnowledgeBuildError(
                    "Corpus content differs from the existing manifest; use --force "
                    "to replace only the derived manifest."
                )
        write_manifest_atomic(self.output_path, manifest)
        return CorpusBuildResult(
            manifest=manifest,
            output_path=relative_output,
            written=True,
            unchanged=False,
            dry_run=False,
        )

    def list_documents(
        self,
        *,
        include_draft: bool = False,
        include_deprecated: bool = False,
    ) -> list[CorpusListItem]:
        documents, _, chunks = self._current_corpus(
            include_draft=include_draft,
            include_deprecated=include_deprecated,
        )
        chunk_count: dict[str, int] = {}
        for chunk in chunks:
            chunk_count[chunk.document_id] = chunk_count.get(chunk.document_id, 0) + 1
        return [
            CorpusListItem(
                document_id=document.metadata.document_id,
                title=document.metadata.title,
                category=document.metadata.category,
                status=document.metadata.status,
                knowledge_version=document.metadata.knowledge_version,
                source_id=document.metadata.source_id,
                chunk_count=chunk_count.get(document.metadata.document_id, 0),
                file_sha256=document.file_sha256,
            )
            for document in documents
        ]

    def inspect_document(
        self,
        document_id: str,
        *,
        include_draft: bool = False,
        include_deprecated: bool = False,
    ) -> dict[str, Any]:
        documents, _, chunks = self._current_corpus(
            include_draft=include_draft,
            include_deprecated=include_deprecated,
        )
        document = next(
            (
                item
                for item in documents
                if item.metadata.document_id == document_id
            ),
            None,
        )
        if document is None:
            raise KnowledgeNotFoundError(f"Document not found: {document_id}.")
        return {
            **document.metadata.model_dump(mode="json", exclude_none=True),
            "relative_path": document.relative_path,
            "file_sha256": document.file_sha256,
            "chunk_ids": [
                item.chunk_id for item in chunks if item.document_id == document_id
            ],
        }

    def inspect_chunk(
        self,
        chunk_id: str,
        *,
        include_draft: bool = False,
        include_deprecated: bool = False,
    ) -> KnowledgeChunk:
        _, _, chunks = self._current_corpus(
            include_draft=include_draft,
            include_deprecated=include_deprecated,
        )
        chunk = next((item for item in chunks if item.chunk_id == chunk_id), None)
        if chunk is None:
            raise KnowledgeNotFoundError(f"Chunk not found: {chunk_id}.")
        return chunk
