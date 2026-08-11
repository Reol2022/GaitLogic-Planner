from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from server.knowledge_retrieval.enums import KnowledgeCategory
from server.knowledge_retrieval.errors import KnowledgeVectorStoreError
from server.knowledge_retrieval.retrieval_schemas import RetrievalFilters
from server.knowledge_retrieval.vector_stores.qdrant import QdrantVectorStore
from tests.knowledge_index_helpers import vector_record


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("qdrant_client") is None,
    reason="qdrant-client is an optional dependency",
)


def _store(tmp_path: Path, name: str = "gaitlogic_test_collection") -> QdrantVectorStore:
    return QdrantVectorStore(
        collection_name=name,
        expected_dimensions=2,
        local_path=tmp_path / "qdrant",
    )


def test_qdrant_dense_store_build_search_filter_and_manifest_records(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    try:
        store.build(
            [
                vector_record(
                    chunk_id="recovery",
                    vector=[1, 0],
                    category=KnowledgeCategory.RECOVERY,
                    tags=["fatigue", "recovery"],
                    language="zh-CN",
                ),
                vector_record(
                    chunk_id="threshold",
                    vector=[0, 1],
                    category=KnowledgeCategory.THRESHOLD,
                    tags=["threshold"],
                    language="en-US",
                ),
            ]
        )
        results = store.search(
            [1, 0],
            top_k=5,
            filters=RetrievalFilters(
                categories=[KnowledgeCategory.RECOVERY],
                tags=["fatigue"],
                language="zh-CN",
            ),
        )
        assert [item.chunk_id for item in results] == ["recovery"]
        assert store.validate().record_count == 2
        assert [item.chunk_id for item in store.records()] == ["recovery", "threshold"]
    finally:
        store.close()


def test_qdrant_payload_excludes_sensitive_or_raw_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        store.build([vector_record()])
        points, _ = store.client.scroll(
            store.collection_name,
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        payload = points[0].payload or {}
        forbidden = {
            "content",
            "query",
            "prompt",
            "user_id",
            "api_key",
            "token",
            "database_url",
            "vector",
        }
        assert forbidden.isdisjoint(payload)
        assert payload["chunk_id"] == "doc#section#001"
    finally:
        store.close()


def test_qdrant_rejects_duplicate_or_invalid_query(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        with pytest.raises(KnowledgeVectorStoreError, match="duplicate"):
            store.build([vector_record(), vector_record()])
        store.build([vector_record()])
        with pytest.raises(KnowledgeVectorStoreError, match="dimensions or top_k"):
            store.search([float("nan"), 0], top_k=1)
    finally:
        store.close()
