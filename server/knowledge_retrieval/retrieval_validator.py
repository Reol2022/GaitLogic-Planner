from __future__ import annotations

from server.knowledge_retrieval.embeddings.base import EmbeddingProvider
from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.index_schemas import IndexManifest


def validate_retrieval_binding(
    manifest: IndexManifest,
    provider: EmbeddingProvider,
    *,
    corpus_root_hash: str,
) -> None:
    if manifest.corpus_root_hash != corpus_root_hash:
        raise KnowledgeRetrievalError("Knowledge index is stale.")
    if manifest.embedding_provider != provider.provider_name:
        raise KnowledgeRetrievalError("Embedding provider does not match the index.")
    if manifest.embedding_model != provider.model_name:
        raise KnowledgeRetrievalError("Embedding model does not match the index.")
    if provider.dimensions not in {0, manifest.embedding_dimensions}:
        raise KnowledgeRetrievalError("Embedding dimensions do not match the index.")
