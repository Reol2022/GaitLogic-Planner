from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.knowledge_retrieval.enums import KnowledgeCategory
from server.knowledge_retrieval.errors import KnowledgeVectorStoreError
from server.knowledge_retrieval.retrieval_schemas import RetrievalFilters
from server.knowledge_retrieval.vector_stores.exact_cosine import (
    ExactCosineVectorStore,
    cosine_similarity,
)
from tests.knowledge_index_helpers import vector_record


def test_exact_cosine_build_search_and_stable_sort(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    store.build(
        [
            vector_record(chunk_id="b", vector=[1, 0]),
            vector_record(chunk_id="a", vector=[1, 0]),
            vector_record(chunk_id="c", vector=[0, 1]),
        ]
    )
    results = store.search([1, 0], top_k=2)
    assert [result.chunk_id for result in results] == ["a", "b"]
    assert results[0].score == pytest.approx(1)
    assert store.validate().record_count == 3


def test_filters_category_tag_and_language(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    store.build(
        [
            vector_record(
                chunk_id="recovery",
                category=KnowledgeCategory.RECOVERY,
                tags=["fatigue", "recovery"],
                language="zh-CN",
            ),
            vector_record(
                chunk_id="threshold",
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
    assert [result.chunk_id for result in results] == ["recovery"]


def test_duplicate_and_dimension_mismatch_are_rejected(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    with pytest.raises(KnowledgeVectorStoreError, match="duplicate"):
        store.build([vector_record(), vector_record()])
    with pytest.raises(KnowledgeVectorStoreError, match="dimensions"):
        store.build([vector_record(vector=[1, 0, 0])])
    with pytest.raises(KnowledgeVectorStoreError, match="dimensions"):
        cosine_similarity([1], [1, 0])


def test_empty_store_and_close(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    store.build([])
    assert store.search([1, 0], top_k=4) == []
    store.close()
    with pytest.raises(KnowledgeVectorStoreError, match="closed"):
        store.validate()


def test_existing_and_corrupt_store_are_rejected(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    store.build([vector_record()])
    with pytest.raises(KnowledgeVectorStoreError, match="already exists"):
        store.build([vector_record(chunk_id="second")])
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(KnowledgeVectorStoreError, match="corrupted"):
        store.validate()


def test_non_finite_query_is_rejected(tmp_path: Path) -> None:
    store = ExactCosineVectorStore(tmp_path / "store", expected_dimensions=2)
    store.build([vector_record()])
    with pytest.raises(KnowledgeVectorStoreError, match="finite"):
        store.search([float("nan"), 0], top_k=1)
