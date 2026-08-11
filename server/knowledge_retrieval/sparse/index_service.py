"""Immutable local BM25 index publication and freshness validation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from server.knowledge_retrieval.enums import KnowledgeDocumentStatus
from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.index_manifest import file_sha256
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.paths import ensure_within_root
from server.knowledge_retrieval.sparse.bm25 import ANALYZER_VERSION, BM25Analyzer, BM25Index, Bm25Document
from server.knowledge_retrieval.sparse.schemas import Bm25IndexManifest, Bm25IndexPayload
from server.knowledge_retrieval.validator import KnowledgeCorpusValidator


DEFAULT_BM25_INDEX_ROOT = Path("var/knowledge_bm25_indexes")
BM25_INDEX_FILENAME = "bm25-index.json"


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class Bm25IndexService:
    def __init__(
        self,
        *,
        repository_root: Path | None = None,
        corpus_manifest_path: Path = Path("knowledge/manifests/corpus-v1.json"),
        index_root: Path = DEFAULT_BM25_INDEX_ROOT,
        analyzer: BM25Analyzer | None = None,
    ) -> None:
        self.repository_root = (repository_root or Path.cwd()).resolve()
        self.corpus_manifest_path = self._resolve(corpus_manifest_path, "Corpus manifest")
        self.index_root = self._resolve(index_root, "BM25 index root")
        self.analyzer = analyzer or BM25Analyzer()

    def _resolve(self, path: Path, label: str) -> Path:
        resolved = path.resolve() if path.is_absolute() else (self.repository_root / path).resolve()
        try:
            ensure_within_root(resolved, self.repository_root)
        except Exception as exc:
            raise KnowledgeIndexError(f"{label} must stay inside the repository.") from exc
        return resolved

    def _corpus(self):
        corpus = load_manifest(self.corpus_manifest_path)
        KnowledgeCorpusValidator().validate_manifest(corpus)
        return corpus

    def _documents(self, corpus) -> list[Bm25Document]:
        result: list[Bm25Document] = []
        for chunk in corpus.chunks:
            if chunk.metadata.status != KnowledgeDocumentStatus.ACTIVE:
                continue
            terms = BM25Analyzer.tokenize(chunk.content)
            result.append(
                Bm25Document(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content_sha256=chunk.content_sha256,
                    category=chunk.category.value,
                    tags=tuple(sorted(chunk.tags)),
                    language=chunk.metadata.language,
                    term_frequencies=dict(__import__("collections").Counter(terms)),
                    document_length=len(terms),
                )
            )
        return sorted(result, key=lambda item: item.chunk_id)

    def _manifest(self, corpus, documents: list[Bm25Document]) -> Bm25IndexManifest:
        index = BM25Index(documents)
        identity = {
            "corpus_root_hash": corpus.root_hash,
            "strategy": "bm25_v1",
            "analyzer_version": ANALYZER_VERSION,
            "k1": index.k1,
            "b": index.b,
            "chunk_hashes": {item.chunk_id: item.content_sha256 for item in documents},
        }
        index_id = f"bm25-{_stable_hash(identity)[:24]}"
        root_payload = {
            **identity,
            "index_id": index_id,
            "corpus_manifest_sha256": file_sha256(self.corpus_manifest_path),
        }
        return Bm25IndexManifest(
            index_id=index_id,
            corpus_root_hash=corpus.root_hash,
            corpus_manifest_sha256=file_sha256(self.corpus_manifest_path),
            analyzer_version=ANALYZER_VERSION,
            k1=index.k1,
            b=index.b,
            chunk_count=len(documents),
            chunk_ids=[item.chunk_id for item in documents],
            chunk_content_hashes={item.chunk_id: item.content_sha256 for item in documents},
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            root_hash=_stable_hash(root_payload),
        )

    @staticmethod
    def _serialize_documents(documents: list[Bm25Document]) -> list[dict[str, object]]:
        return [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "content_sha256": item.content_sha256,
                "category": item.category,
                "tags": list(item.tags),
                "language": item.language,
                "term_frequencies": item.term_frequencies,
                "document_length": item.document_length,
            }
            for item in documents
        ]

    @staticmethod
    def _deserialize_documents(payload: Bm25IndexPayload) -> list[Bm25Document]:
        documents: list[Bm25Document] = []
        for item in payload.documents:
            try:
                documents.append(
                    Bm25Document(
                        chunk_id=str(item["chunk_id"]), document_id=str(item["document_id"]),
                        content_sha256=str(item["content_sha256"]), category=str(item["category"]),
                        tags=tuple(str(value) for value in item["tags"]), language=str(item["language"]),
                        term_frequencies={str(key): int(value) for key, value in dict(item["term_frequencies"]).items()},
                        document_length=int(item["document_length"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise KnowledgeIndexError("BM25 index payload is invalid.") from exc
        return documents

    def build(self) -> Bm25IndexManifest:
        corpus = self._corpus()
        documents = self._documents(corpus)
        if not documents:
            raise KnowledgeIndexError("Cannot build a BM25 index from an empty corpus.")
        manifest = self._manifest(corpus, documents)
        target = self.index_root / manifest.index_id
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = self.validate(manifest.index_id)
            if existing.root_hash == manifest.root_hash:
                return existing
            raise KnowledgeIndexError("BM25 index identity collision detected.")
        staging = self.index_root / f".{manifest.index_id}.{uuid4().hex}.tmp"
        try:
            staging.mkdir()
            payload = Bm25IndexPayload(manifest=manifest, documents=self._serialize_documents(documents))
            (staging / BM25_INDEX_FILENAME).write_text(
                json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(staging, target)
            return self.validate(manifest.index_id)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def load(self, index_id: str) -> tuple[Bm25IndexManifest, BM25Index]:
        path = self.index_root / index_id / BM25_INDEX_FILENAME
        try:
            ensure_within_root(path, self.index_root)
            payload = Bm25IndexPayload.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise KnowledgeIndexError("BM25 index is unavailable or invalid.") from exc
        return payload.manifest, BM25Index(self._deserialize_documents(payload), k1=payload.manifest.k1, b=payload.manifest.b)

    def validate(self, index_id: str) -> Bm25IndexManifest:
        corpus = self._corpus()
        manifest, index = self.load(index_id)
        if manifest.corpus_root_hash != corpus.root_hash or manifest.corpus_manifest_sha256 != file_sha256(self.corpus_manifest_path):
            raise KnowledgeIndexError("BM25 index corpus binding is stale; rebuild required.")
        if manifest.strategy != "bm25_v1" or manifest.analyzer_version != ANALYZER_VERSION:
            raise KnowledgeIndexError("BM25 index analyzer binding is stale; rebuild required.")
        if manifest.chunk_count != len(index.documents) or sorted(manifest.chunk_ids) != sorted(item.chunk_id for item in index.documents):
            raise KnowledgeIndexError("BM25 index chunk references are invalid.")
        if any(manifest.chunk_content_hashes[item.chunk_id] != item.content_sha256 for item in index.documents):
            raise KnowledgeIndexError("BM25 index content hashes are invalid.")
        return manifest

    def latest_index_id(self) -> str:
        if not self.index_root.exists():
            raise KnowledgeIndexError("No BM25 indexes are available.")
        candidates = sorted(path.name for path in self.index_root.iterdir() if path.is_dir() and path.name.startswith("bm25-"))
        if not candidates:
            raise KnowledgeIndexError("No BM25 indexes are available.")
        return candidates[-1]
