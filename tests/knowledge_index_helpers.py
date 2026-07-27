from __future__ import annotations

from pathlib import Path
from typing import Any

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.enums import (
    KnowledgeCategory,
    KnowledgeDocumentStatus,
)
from server.knowledge_retrieval.index_schemas import VectorRecord
from server.knowledge_retrieval.index_service import KnowledgeIndexService


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORPUS_MANIFEST = REPOSITORY_ROOT / "knowledge/manifests/corpus-v1.json"


def prepare_repository(tmp_path: Path) -> KnowledgeIndexService:
    target = tmp_path / "knowledge/manifests"
    target.mkdir(parents=True)
    (target / "corpus-v1.json").write_bytes(CORPUS_MANIFEST.read_bytes())
    return KnowledgeIndexService(repository_root=tmp_path)


def build_test_index(
    tmp_path: Path,
    *,
    dimensions: int = 32,
) -> tuple[KnowledgeIndexService, str]:
    service = prepare_repository(tmp_path)
    result = service.build(
        DeterministicEmbeddingProvider(dimensions=dimensions)
    )
    return service, result.manifest.index_id


def vector_record(
    *,
    chunk_id: str = "doc#section#001",
    vector: list[float] | None = None,
    category: KnowledgeCategory = KnowledgeCategory.RECOVERY,
    tags: list[str] | None = None,
    language: str = "zh-CN",
    **overrides: Any,
) -> VectorRecord:
    payload: dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": "doc",
        "content_sha256": "a" * 64,
        "vector": vector or [1.0, 0.0],
        "category": category,
        "tags": tags or ["fatigue"],
        "source_id": "source",
        "knowledge_version": "1.0.0",
        "language": language,
        "status": KnowledgeDocumentStatus.ACTIVE,
        "section": "核心原则",
        "relative_path": "documents/doc.md",
    }
    payload.update(overrides)
    return VectorRecord(**payload)
