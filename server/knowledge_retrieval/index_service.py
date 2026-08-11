from __future__ import annotations

import math
import os
from pathlib import Path
import shutil
from uuid import uuid4

from server.knowledge_retrieval.embeddings.base import EmbeddingProvider
from server.knowledge_retrieval.enums import KnowledgeDocumentStatus
from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.index_manifest import (
    INDEX_MANIFEST_FILENAME,
    build_index_manifest,
    calculate_index_id,
    file_sha256,
    index_identity_payload,
    load_index_manifest,
    validate_index_manifest,
    vector_sha256,
    write_index_manifest,
)
from server.knowledge_retrieval.index_schemas import (
    IndexBuildPlan,
    IndexBuildResult,
    IndexListItem,
    IndexManifest,
    VectorRecord,
)
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.paths import ensure_within_root
from server.knowledge_retrieval.validator import KnowledgeCorpusValidator
from server.knowledge_retrieval.vector_stores.factory import (
    create_vector_store,
    vector_store_name,
)


DEFAULT_CORPUS_MANIFEST = Path("knowledge/manifests/corpus-v1.json")
DEFAULT_INDEX_ROOT = Path("var/knowledge_indexes")


class KnowledgeIndexService:
    def __init__(
        self,
        *,
        repository_root: Path | None = None,
        corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST,
        index_root: Path = DEFAULT_INDEX_ROOT,
        vector_store: str = "exact",
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        qdrant_collection_prefix: str = "gaitlogic",
    ) -> None:
        self.repository_root = (repository_root or Path.cwd()).resolve()
        self.corpus_manifest_path = self._resolve_repository_path(
            corpus_manifest_path,
            label="Corpus manifest",
        )
        self.index_root = self._resolve_repository_path(
            index_root,
            label="Index root",
        )
        self.vector_store = vector_store
        self.vector_store_name = vector_store_name(vector_store)
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.qdrant_collection_prefix = qdrant_collection_prefix

    def _store(
        self,
        directory: Path,
        *,
        index_id: str,
        dimensions: int,
        vector_store: str | None = None,
    ):
        return create_vector_store(
            kind=vector_store or self.vector_store,
            directory=directory,
            index_id=index_id,
            dimensions=dimensions,
            qdrant_url=self.qdrant_url,
            qdrant_api_key=self.qdrant_api_key,
            qdrant_prefix=self.qdrant_collection_prefix,
        )

    def _resolve_repository_path(self, path: Path, *, label: str) -> Path:
        resolved = path.resolve() if path.is_absolute() else (
            self.repository_root / path
        ).resolve()
        try:
            ensure_within_root(resolved, self.repository_root)
        except Exception as exc:
            raise KnowledgeIndexError(
                f"{label} must stay inside the repository."
            ) from exc
        return resolved

    def _corpus(self):
        manifest = load_manifest(self.corpus_manifest_path)
        KnowledgeCorpusValidator().validate_manifest(manifest)
        return manifest

    @staticmethod
    def _active_chunks(manifest):
        return [
            chunk
            for chunk in manifest.chunks
            if chunk.metadata.status == KnowledgeDocumentStatus.ACTIVE
        ]

    def plan(self, provider: EmbeddingProvider) -> IndexBuildPlan:
        corpus = self._corpus()
        chunks = self._active_chunks(corpus)
        dimensions = provider.dimensions or None
        identity_dimensions = dimensions or 1
        index_id = calculate_index_id(
            **index_identity_payload(
                corpus_root_hash=corpus.root_hash,
                embedding_provider=provider.provider_name,
                embedding_model=provider.model_name,
                embedding_dimensions=identity_dimensions,
                vector_store=self.vector_store_name,
            )
        )
        relative = (
            self.index_root / index_id
        ).relative_to(self.repository_root).as_posix()
        return IndexBuildPlan(
            provider=provider.provider_name,
            model=provider.model_name,
            vector_store=self.vector_store_name,
            dimensions=dimensions,
            chunk_count=len(chunks),
            estimated_batches=math.ceil(len(chunks) / provider.max_batch_size),
            corpus_root_hash=corpus.root_hash,
            index_root=relative,
        )

    def _records(
        self,
        provider: EmbeddingProvider,
    ) -> tuple[list[VectorRecord], list[str], int]:
        corpus = self._corpus()
        chunks = self._active_chunks(corpus)
        vectors: list[list[float]] = []
        warnings: list[str] = []
        for start in range(0, len(chunks), provider.max_batch_size):
            batch_chunks = chunks[start : start + provider.max_batch_size]
            batch = provider.embed_documents(
                [chunk.content for chunk in batch_chunks]
            )
            if len(batch.vectors) != len(batch_chunks):
                raise KnowledgeIndexError(
                    "Embedding provider returned an unexpected vector count."
                )
            vectors.extend(batch.vectors)
            warnings.extend(batch.warnings)
        dimensions = provider.dimensions
        if not dimensions or any(len(vector) != dimensions for vector in vectors):
            raise KnowledgeIndexError("Embedding dimensions are inconsistent.")
        records = [
            VectorRecord(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                content_sha256=chunk.content_sha256,
                vector=vector,
                category=chunk.category,
                tags=chunk.tags,
                source_id=chunk.source_id,
                knowledge_version=chunk.knowledge_version,
                language=chunk.metadata.language,
                status=chunk.metadata.status,
                section=chunk.section,
                relative_path=chunk.metadata.document_path,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        return records, sorted(set(warnings)), dimensions

    def build(
        self,
        provider: EmbeddingProvider,
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> IndexBuildPlan | IndexBuildResult:
        if dry_run:
            return self.plan(provider)
        staging: Path | None = None
        backup: Path | None = None
        target: Path | None = None
        try:
            corpus = self._corpus()
            records, warnings, dimensions = self._records(provider)
            if provider.provider_name != "deterministic_test":
                warnings.append(
                    "Remote embedding models may change over time; identical corpus "
                    "input does not guarantee identical future vectors."
                )
            manifest = build_index_manifest(
                corpus_root_hash=corpus.root_hash,
                corpus_manifest_sha256=file_sha256(self.corpus_manifest_path),
                embedding_provider=provider.provider_name,
                embedding_model=provider.model_name,
                embedding_dimensions=dimensions,
                embedding_normalized=provider.normalized,
                records=records,
                warnings=warnings,
                vector_store=self.vector_store_name,
            )
            self.index_root.mkdir(parents=True, exist_ok=True)
            target = self.index_root / manifest.index_id
            staging = self.index_root / f".{manifest.index_id}.{uuid4().hex}.tmp"
            backup = self.index_root / f".{manifest.index_id}.{uuid4().hex}.bak"
            relative = target.relative_to(self.repository_root).as_posix()
            if target.exists():
                existing = load_index_manifest(target / INDEX_MANIFEST_FILENAME)
                self._validate_directory(target, corpus.root_hash)
                if existing.root_hash == manifest.root_hash:
                    return IndexBuildResult(
                        manifest=existing,
                        relative_path=relative,
                        written=False,
                        unchanged=True,
                    )
                if not force:
                    raise KnowledgeIndexError(
                        "Index already exists with different vectors; use --force "
                        "to replace only the derived index."
                    )
                if self.vector_store_name != "exact_cosine_v1":
                    raise KnowledgeIndexError(
                        "Force-replacing a Qdrant index is intentionally unsupported; "
                        "publish a new immutable index identity instead."
                    )
            staging.mkdir()
            store = self._store(
                staging,
                index_id=manifest.index_id,
                dimensions=dimensions,
            )
            try:
                store.build(records)
            finally:
                store.close()
            write_index_manifest(staging / INDEX_MANIFEST_FILENAME, manifest)
            self._validate_directory(staging, corpus.root_hash)
            if target.exists():
                os.replace(target, backup)
            os.replace(staging, target)
            if backup.exists():
                shutil.rmtree(backup)
            return IndexBuildResult(
                manifest=manifest,
                relative_path=relative,
                written=True,
                unchanged=False,
            )
        except Exception:
            if staging is not None and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            if (
                backup is not None
                and target is not None
                and backup.exists()
                and not target.exists()
            ):
                os.replace(backup, target)
            raise
        finally:
            provider.close()

    def _validate_directory(
        self,
        directory: Path,
        current_corpus_root_hash: str,
    ) -> IndexManifest:
        manifest = load_index_manifest(directory / INDEX_MANIFEST_FILENAME)
        validate_index_manifest(manifest)
        if manifest.corpus_root_hash != current_corpus_root_hash:
            raise KnowledgeIndexError("Index corpus root hash is stale.")
        if manifest.corpus_manifest_sha256 != file_sha256(
            self.corpus_manifest_path
        ):
            raise KnowledgeIndexError("Index corpus manifest file hash is stale.")
        store = self._store(
            directory,
            index_id=manifest.index_id,
            dimensions=manifest.embedding_dimensions,
            vector_store=manifest.vector_store,
        )
        try:
            records = store.records()
            validation = store.validate()
        finally:
            store.close()
        if validation.record_count != manifest.chunk_count:
            raise KnowledgeIndexError("Vector store record count is invalid.")
        ids = [record.chunk_id for record in records]
        if sorted(ids) != sorted(manifest.chunk_ids):
            raise KnowledgeIndexError("Vector store chunk references are invalid.")
        for record in records:
            if manifest.chunk_content_hashes[record.chunk_id] != record.content_sha256:
                raise KnowledgeIndexError("Vector store content hash is invalid.")
            if manifest.vector_hashes[record.chunk_id] != vector_sha256(record.vector):
                raise KnowledgeIndexError("Vector store vector hash is invalid.")
        return manifest

    def validate(self, index_id: str) -> IndexManifest:
        corpus = self._corpus()
        directory = self.index_root / index_id
        ensure_within_root(directory, self.index_root)
        return self._validate_directory(directory, corpus.root_hash)

    def list_indexes(self) -> list[IndexListItem]:
        if not self.index_root.exists():
            return []
        items: list[IndexListItem] = []
        for directory in sorted(self.index_root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            manifest = load_index_manifest(directory / INDEX_MANIFEST_FILENAME)
            items.append(
                IndexListItem(
                    index_id=manifest.index_id,
                    corpus_root_hash=manifest.corpus_root_hash,
                    embedding_provider=manifest.embedding_provider,
                    embedding_model=manifest.embedding_model,
                    embedding_dimensions=manifest.embedding_dimensions,
                    vector_store=manifest.vector_store,
                    chunk_count=manifest.chunk_count,
                    root_hash=manifest.root_hash,
                    created_at=manifest.created_at,
                )
            )
        return items

    def inspect(self, index_id: str) -> dict[str, object]:
        manifest = self.validate(index_id)
        relative = (
            self.index_root / index_id
        ).relative_to(self.repository_root).as_posix()
        return {
            **manifest.model_dump(mode="json"),
            "relative_path": relative,
        }

    def latest_index_id(self) -> str:
        items = self.list_indexes()
        if not items:
            raise KnowledgeIndexError("No knowledge indexes are available.")
        return sorted(
            items,
            key=lambda item: (item.created_at, item.index_id),
            reverse=True,
        )[0].index_id

    def load_records(self, index_id: str) -> tuple[IndexManifest, list[VectorRecord]]:
        manifest = self.validate(index_id)
        store = self._store(
            self.index_root / index_id,
            index_id=index_id,
            dimensions=manifest.embedding_dimensions,
            vector_store=manifest.vector_store,
        )
        try:
            records = store.records()
        finally:
            store.close()
        return manifest, records
