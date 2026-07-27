from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from server.knowledge_retrieval.errors import KnowledgeVectorStoreError
from server.knowledge_retrieval.index_schemas import (
    VectorRecord,
    VectorSearchResult,
    VectorStoreValidationResult,
)
from server.knowledge_retrieval.retrieval_schemas import RetrievalFilters


STORE_FILENAME = "records.json"
_RECORDS_ADAPTER = TypeAdapter(list[VectorRecord])


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise KnowledgeVectorStoreError("Vector dimensions do not match.")
    if not all(math.isfinite(value) for value in [*left, *right]):
        raise KnowledgeVectorStoreError("Vectors must contain finite values.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        raise KnowledgeVectorStoreError("Vector norm must be positive.")
    score = sum(a * b for a, b in zip(left, right, strict=True))
    score /= left_norm * right_norm
    return max(-1.0, min(1.0, score))


class ExactCosineVectorStore:
    store_name = "exact_cosine_v1"

    def __init__(self, directory: Path, *, expected_dimensions: int) -> None:
        self.directory = directory
        self.path = directory / STORE_FILENAME
        self.expected_dimensions = expected_dimensions
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise KnowledgeVectorStoreError("Vector store is closed.")

    def _load(self) -> list[VectorRecord]:
        self._ensure_open()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            records = _RECORDS_ADAPTER.validate_python(payload)
        except (OSError, ValueError, ValidationError) as exc:
            raise KnowledgeVectorStoreError("Vector store is missing or corrupted.") from exc
        self._validate_records(records)
        return records

    def _validate_records(self, records: list[VectorRecord]) -> None:
        ids = [record.chunk_id for record in records]
        if len(ids) != len(set(ids)):
            raise KnowledgeVectorStoreError("Vector store contains duplicate chunk IDs.")
        if any(len(record.vector) != self.expected_dimensions for record in records):
            raise KnowledgeVectorStoreError(
                "Vector store contains inconsistent dimensions."
            )

    def build(self, records: list[VectorRecord]) -> None:
        self._ensure_open()
        if self.path.exists():
            raise KnowledgeVectorStoreError("Vector store already exists.")
        self._validate_records(records)
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = [
            record.model_dump(mode="json")
            for record in sorted(records, key=lambda item: item.chunk_id)
        ]
        try:
            self.path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except OSError as exc:
            raise KnowledgeVectorStoreError("Failed to write vector store.") from exc

    @staticmethod
    def _matches(record: VectorRecord, filters: RetrievalFilters | None) -> bool:
        if filters is None:
            return True
        if filters.categories and record.category not in filters.categories:
            return False
        if filters.tags and not set(filters.tags).issubset(set(record.tags)):
            return False
        if filters.language and record.language != filters.language:
            return False
        return True

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> list[VectorSearchResult]:
        if top_k < 1:
            raise KnowledgeVectorStoreError("top_k must be positive.")
        if len(query_vector) != self.expected_dimensions:
            raise KnowledgeVectorStoreError("Query vector dimensions do not match.")
        scored = [
            VectorSearchResult(
                chunk_id=record.chunk_id,
                score=cosine_similarity(query_vector, record.vector),
            )
            for record in self._load()
            if self._matches(record, filters)
        ]
        return sorted(scored, key=lambda item: (-item.score, item.chunk_id))[:top_k]

    def validate(self) -> VectorStoreValidationResult:
        records = self._load()
        return VectorStoreValidationResult(
            valid=True,
            record_count=len(records),
            dimensions=self.expected_dimensions if records else 0,
        )

    def records(self) -> list[VectorRecord]:
        return self._load()

    def close(self) -> None:
        self._closed = True
