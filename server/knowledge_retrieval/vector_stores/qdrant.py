"""Dense-only Qdrant adapter with a deliberately minimal payload contract."""

from __future__ import annotations

import math
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from server.knowledge_retrieval.enums import KnowledgeDocumentStatus
from server.knowledge_retrieval.errors import KnowledgeVectorStoreError
from server.knowledge_retrieval.index_schemas import (
    VectorRecord,
    VectorSearchResult,
    VectorStoreValidationResult,
)
from server.knowledge_retrieval.retrieval_schemas import RetrievalFilters


class QdrantVectorStore:
    """Qdrant implementation for versioned public training-knowledge indexes.

    Payloads contain only public corpus identifiers and filter metadata.  Query
    text, user data, credentials, raw chunks, and vectors are never payloads.
    Vectors are fetched only by the internal validation path to verify the
    manifest hashes created at indexing time.
    """

    store_name = "qdrant_dense_v1"

    def __init__(
        self,
        *,
        collection_name: str,
        expected_dimensions: int,
        url: str | None = None,
        api_key: str | None = None,
        local_path: Path | None = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise KnowledgeVectorStoreError("Qdrant support is not installed.") from exc
        if not collection_name.replace("_", "").replace("-", "").isalnum():
            raise KnowledgeVectorStoreError("Qdrant collection name is invalid.")
        if expected_dimensions < 1:
            raise KnowledgeVectorStoreError("Qdrant dimensions are invalid.")
        self.collection_name = collection_name
        self.expected_dimensions = expected_dimensions
        self.client = (
            QdrantClient(path=str(local_path))
            if local_path is not None
            else QdrantClient(url=url, api_key=api_key)
        )
        self._closed = False

    @staticmethod
    def _payload(record: VectorRecord) -> dict[str, object]:
        return {
            "chunk_id": record.chunk_id,
            "document_id": record.document_id,
            "content_sha256": record.content_sha256,
            "category": record.category.value,
            "tags": record.tags,
            "source_id": record.source_id,
            "knowledge_version": record.knowledge_version,
            "language": record.language,
            "status": record.status.value,
            "section": record.section,
            "relative_path": record.relative_path,
        }

    def build(self, records: list[VectorRecord]) -> None:
        from qdrant_client.models import Distance, PointStruct, VectorParams

        if self.client.collection_exists(self.collection_name):
            raise KnowledgeVectorStoreError("Qdrant collection already exists.")
        if len({record.chunk_id for record in records}) != len(records):
            raise KnowledgeVectorStoreError("Vector store contains duplicate chunk IDs.")
        if any(len(record.vector) != self.expected_dimensions for record in records):
            raise KnowledgeVectorStoreError(
                "Vector store contains inconsistent dimensions."
            )
        created = False
        try:
            self.client.create_collection(
                self.collection_name,
                vectors_config=VectorParams(
                    size=self.expected_dimensions,
                    distance=Distance.COSINE,
                ),
            )
            created = True
            self.client.upsert(
                self.collection_name,
                points=[
                    PointStruct(
                        id=str(uuid5(NAMESPACE_URL, f"gaitlogic:{record.chunk_id}")),
                        vector=record.vector,
                        payload=self._payload(record),
                    )
                    for record in records
                ],
                wait=True,
            )
        except KnowledgeVectorStoreError:
            raise
        except Exception as exc:
            if created:
                try:
                    self.client.delete_collection(self.collection_name)
                except Exception:
                    # The primary failure remains the only public error.  The
                    # next validation will safely report a missing collection.
                    pass
            raise KnowledgeVectorStoreError("Qdrant index build failed.") from exc

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: RetrievalFilters | None = None,
    ) -> list[VectorSearchResult]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        if (
            len(query_vector) != self.expected_dimensions
            or top_k < 1
            or not all(math.isfinite(float(item)) for item in query_vector)
        ):
            raise KnowledgeVectorStoreError("Query vector dimensions or top_k are invalid.")
        must = []
        if filters and filters.categories:
            must.append(
                FieldCondition(
                    key="category",
                    match=MatchAny(any=[item.value for item in filters.categories]),
                )
            )
        if filters and filters.tags:
            must.extend(
                FieldCondition(key="tags", match=MatchValue(value=tag))
                for tag in filters.tags
            )
        if filters and filters.language:
            must.append(
                FieldCondition(
                    key="language",
                    match=MatchValue(value=filters.language),
                )
            )
        try:
            points = self.client.query_points(
                self.collection_name,
                query=query_vector,
                query_filter=Filter(must=must) if must else None,
                limit=top_k,
                with_payload=["chunk_id"],
                with_vectors=False,
            ).points
            return [
                VectorSearchResult(
                    chunk_id=str(point.payload["chunk_id"]),
                    score=float(point.score),
                )
                for point in points
            ]
        except Exception as exc:
            raise KnowledgeVectorStoreError("Qdrant search is unavailable.") from exc

    def validate(self) -> VectorStoreValidationResult:
        try:
            info = self.client.get_collection(self.collection_name)
            return VectorStoreValidationResult(
                valid=True,
                record_count=int(info.points_count or 0),
                dimensions=self.expected_dimensions,
            )
        except Exception as exc:
            raise KnowledgeVectorStoreError("Qdrant collection is unavailable.") from exc

    def records(self) -> list[VectorRecord]:
        records: list[VectorRecord] = []
        offset = None
        try:
            while True:
                points, offset = self.client.scroll(
                    self.collection_name,
                    offset=offset,
                    limit=256,
                    with_payload=True,
                    with_vectors=True,
                )
                for point in points:
                    payload = point.payload or {}
                    if not isinstance(point.vector, list):
                        raise KnowledgeVectorStoreError(
                            "Qdrant stored an unsupported vector shape."
                        )
                    records.append(
                        VectorRecord(
                            chunk_id=str(payload["chunk_id"]),
                            document_id=str(payload["document_id"]),
                            content_sha256=str(payload["content_sha256"]),
                            vector=[float(item) for item in point.vector],
                            category=str(payload["category"]),
                            tags=[str(item) for item in payload.get("tags", [])],
                            source_id=str(payload["source_id"]),
                            knowledge_version=str(payload["knowledge_version"]),
                            language=str(payload["language"]),
                            status=KnowledgeDocumentStatus(str(payload["status"])),
                            section=str(payload["section"]),
                            relative_path=str(payload["relative_path"]),
                        )
                    )
                if offset is None:
                    break
        except KnowledgeVectorStoreError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise KnowledgeVectorStoreError("Qdrant stored invalid metadata.") from exc
        except Exception as exc:
            raise KnowledgeVectorStoreError("Qdrant collection is unavailable.") from exc
        return sorted(records, key=lambda item: item.chunk_id)

    def close(self) -> None:
        if not self._closed:
            self.client.close()
            self._closed = True
