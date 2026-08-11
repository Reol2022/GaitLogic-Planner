from __future__ import annotations

from typing import Protocol

from server.knowledge_retrieval.index_schemas import (
    VectorRecord,
    VectorSearchResult,
    VectorStoreValidationResult,
)
from server.knowledge_retrieval.retrieval_schemas import RetrievalFilters


class VectorStore(Protocol):
    store_name: str

    def build(self, records: list[VectorRecord]) -> None:
        ...

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> list[VectorSearchResult]:
        ...

    def validate(self) -> VectorStoreValidationResult:
        ...

    def records(self) -> list[VectorRecord]:
        ...

    def close(self) -> None:
        ...
