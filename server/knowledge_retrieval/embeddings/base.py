from __future__ import annotations

from typing import Protocol

from server.knowledge_retrieval.embeddings.schemas import (
    EmbeddingBatch,
    EmbeddingVector,
)


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int
    normalized: bool
    max_batch_size: int

    def embed_documents(self, texts: list[str]) -> EmbeddingBatch:
        ...

    def embed_query(self, text: str) -> EmbeddingVector:
        ...

    def close(self) -> None:
        ...
