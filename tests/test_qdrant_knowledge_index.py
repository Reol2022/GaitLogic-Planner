from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from tests.knowledge_index_helpers import prepare_repository


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("qdrant_client") is None,
    reason="qdrant-client is an optional dependency",
)


def test_qdrant_index_build_validate_and_retrieve(tmp_path: Path) -> None:
    service = prepare_repository(tmp_path)
    service = type(service)(
        repository_root=tmp_path,
        vector_store="qdrant",
    )
    result = service.build(DeterministicEmbeddingProvider(dimensions=16))

    assert result.manifest.vector_store == "qdrant_dense_v1"
    assert service.validate(result.manifest.index_id).root_hash == result.manifest.root_hash

    retriever = TrainingKnowledgeRetriever(
        index_service=service,
        provider=DeterministicEmbeddingProvider(dimensions=16),
        index_id=result.manifest.index_id,
        vector_store="qdrant",
    )
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(query="threshold training", top_k=2)
    )
    assert response.index_id == result.manifest.index_id
    assert len(response.results) == 2


def test_qdrant_and_exact_return_the_same_filtered_chunk_order(tmp_path: Path) -> None:
    exact_root = tmp_path / "exact"
    qdrant_root = tmp_path / "qdrant"
    exact = prepare_repository(exact_root)
    qdrant = type(exact)(repository_root=qdrant_root, vector_store="qdrant")
    target = qdrant_root / "knowledge/manifests"
    target.mkdir(parents=True)
    target.joinpath("corpus-v1.json").write_bytes(
        exact_root.joinpath("knowledge/manifests/corpus-v1.json").read_bytes()
    )
    provider = DeterministicEmbeddingProvider(dimensions=16)
    exact_result = exact.build(provider)
    qdrant_result = qdrant.build(DeterministicEmbeddingProvider(dimensions=16))
    request = KnowledgeRetrievalRequest(
        query="recovery fatigue",
        top_k=4,
        tags=["recovery"],
    )
    exact_response = TrainingKnowledgeRetriever(
        index_service=exact,
        provider=DeterministicEmbeddingProvider(dimensions=16),
        index_id=exact_result.manifest.index_id,
    ).retrieve(request)
    qdrant_response = TrainingKnowledgeRetriever(
        index_service=qdrant,
        provider=DeterministicEmbeddingProvider(dimensions=16),
        index_id=qdrant_result.manifest.index_id,
        vector_store="qdrant",
    ).retrieve(request)
    assert [item.chunk_id for item in qdrant_response.results] == [
        item.chunk_id for item in exact_response.results
    ]
