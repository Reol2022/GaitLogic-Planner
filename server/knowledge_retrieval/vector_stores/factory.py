from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.errors import KnowledgeVectorStoreError
from server.knowledge_retrieval.vector_stores.base import VectorStore
from server.knowledge_retrieval.vector_stores.exact_cosine import ExactCosineVectorStore
from server.knowledge_retrieval.vector_stores.qdrant import QdrantVectorStore


def vector_store_name(kind: str) -> str:
    if kind in {"exact", ExactCosineVectorStore.store_name}:
        return ExactCosineVectorStore.store_name
    if kind in {"qdrant", QdrantVectorStore.store_name}:
        return QdrantVectorStore.store_name
    raise KnowledgeVectorStoreError("Unsupported vector store.")


def create_vector_store(
    *,
    kind: str,
    directory: Path,
    index_id: str,
    dimensions: int,
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    qdrant_prefix: str = "gaitlogic",
) -> VectorStore:
    store_name = vector_store_name(kind)
    if store_name == ExactCosineVectorStore.store_name:
        return ExactCosineVectorStore(directory / "store", expected_dimensions=dimensions)
    if store_name == QdrantVectorStore.store_name:
        collection = f"{qdrant_prefix}_{index_id.replace('-', '_')}"
        return QdrantVectorStore(
            collection_name=collection,
            expected_dimensions=dimensions,
            url=qdrant_url,
            api_key=qdrant_api_key,
            # Build staging directories are intentionally long.  Keeping one
            # local Qdrant root beside the versioned index directories avoids
            # Windows path-length failures while retaining a stable collection
            # name derived from the immutable index identity.
            local_path=(directory.parent / ".qdrant") if not qdrant_url else None,
        )
    raise AssertionError("vector_store_name returned an unsupported store")
