from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.enums import KnowledgeCategory
from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.retrieval_schemas import (
    MAX_EXCERPT_CHARS,
    KnowledgeRetrievalRequest,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from tests.knowledge_index_helpers import build_test_index


def _retriever(tmp_path: Path):
    service, index_id = build_test_index(tmp_path)
    return (
        TrainingKnowledgeRetriever(
            index_service=service,
            provider=DeterministicEmbeddingProvider(dimensions=32),
            index_id=index_id,
        ),
        service,
        index_id,
    )


def test_retrieves_structured_results_with_stable_order(tmp_path: Path) -> None:
    retriever, _, _ = _retriever(tmp_path)
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(query="疲劳较高时如何调整关键课", top_k=4)
    )
    assert len(response.results) == 4
    assert [item.rank for item in response.results] == [1, 2, 3, 4]
    assert response.results == sorted(
        response.results,
        key=lambda item: (-item.score, item.chunk_id),
    )
    assert all(len(item.excerpt) <= MAX_EXCERPT_CHARS for item in response.results)
    assert all(item.excerpt.startswith("## ") for item in response.results)
    assert all(not Path(item.relative_path).is_absolute() for item in response.results)


def test_category_tag_language_and_min_score_filters(tmp_path: Path) -> None:
    retriever, _, _ = _retriever(tmp_path)
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(
            query="疲劳恢复",
            categories=[KnowledgeCategory.RECOVERY],
            tags=["fatigue"],
            language="zh-CN",
            min_score=-1,
            top_k=10,
        )
    )
    assert response.results
    assert all(item.category == KnowledgeCategory.RECOVERY for item in response.results)
    assert all("fatigue" in item.tags for item in response.results)


def test_empty_result_returns_limitation(tmp_path: Path) -> None:
    retriever, _, _ = _retriever(tmp_path)
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(
            query="test",
            tags=["tag-that-does-not-exist"],
        )
    )
    assert response.results == []
    assert any("No knowledge chunks" in item for item in response.limitations)


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": " "},
        {"query": "x" * 4001},
        {"query": "valid", "top_k": 0},
        {"query": "valid", "top_k": 11},
        {"query": "valid", "categories": ["INVALID"]},
        {"query": "valid", "min_score": 2},
    ],
)
def test_request_validation(payload: dict) -> None:
    with pytest.raises(ValidationError):
        KnowledgeRetrievalRequest(**payload)


def test_stale_or_mismatched_index_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever, service, index_id = _retriever(tmp_path)
    manifest = service.validate(index_id)
    monkeypatch.setattr(
        service,
        "validate",
        lambda value: manifest.model_copy(
            update={"corpus_root_hash": "f" * 64}
        ),
    )
    with pytest.raises(KnowledgeRetrievalError, match="stale"):
        retriever.retrieve(KnowledgeRetrievalRequest(query="test"))


def test_query_is_not_persisted_and_response_is_not_full_document(
    tmp_path: Path,
) -> None:
    retriever, service, index_id = _retriever(tmp_path)
    index_directory = service.index_root / index_id
    before = {
        path.relative_to(index_directory).as_posix(): path.read_bytes()
        for path in index_directory.rglob("*")
        if path.is_file()
    }
    private_query = "虚构查询不得持久化"
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(query=private_query)
    )
    after = {
        path.relative_to(index_directory).as_posix(): path.read_bytes()
        for path in index_directory.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert all(private_query not in value.decode("utf-8") for value in after.values())
    assert all(len(item.excerpt) <= MAX_EXCERPT_CHARS for item in response.results)
    assert "body" not in response.model_dump_json()
