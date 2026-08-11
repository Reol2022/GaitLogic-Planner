from __future__ import annotations

from pathlib import Path
import shutil
import importlib.util

import pytest

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.hybrid.fusion import ReciprocalRankFusion
from server.knowledge_retrieval.hybrid.retriever import HybridKnowledgeRetriever
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer

ROOT = Path(__file__).resolve().parents[1]


def _repository(tmp_path: Path) -> Path:
    (tmp_path / "knowledge/manifests").mkdir(parents=True)
    shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", tmp_path / "knowledge/manifests/corpus-v1.json")
    return tmp_path


def test_rrf_is_stable_merges_duplicates_and_keeps_source_ranks() -> None:
    fused = ReciprocalRankFusion(rank_constant=60).fuse(
        dense_chunk_ids=["c2", "c1", "c1"], bm25_chunk_ids=["c1", "c3"], top_k=3
    )
    assert [item.chunk_id for item in fused] == ["c1", "c2", "c3"]
    assert fused[0].dense_rank == 2 and fused[0].bm25_rank == 1


def test_hybrid_exact_bm25_filters_and_public_schema(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    dense_service = KnowledgeIndexService(repository_root=root, index_root=Path("var/dense"))
    dense = dense_service.build(DeterministicEmbeddingProvider(dimensions=32, environment="test"))
    sparse_service = Bm25IndexService(repository_root=root)
    sparse = sparse_service.build()
    hybrid = HybridKnowledgeRetriever(
        dense_retriever=TrainingKnowledgeRetriever(index_service=dense_service, provider=DeterministicEmbeddingProvider(dimensions=32, environment="test"), index_id=dense.manifest.index_id),
        bm25_retriever=TrainingKnowledgeBm25Retriever(index_service=sparse_service, index_id=sparse.index_id),
        dense_candidate_depth=8, bm25_candidate_depth=8,
    )
    response = hybrid.retrieve(KnowledgeRetrievalRequest(query="training recovery", top_k=4, language="en-US"))
    assert len(response.results) <= 4
    assert response.index_id == "hybrid-rrf"
    assert all(item.rank == index + 1 for index, item in enumerate(response.results))
    assert "fusion_score" not in response.model_dump_json()


@pytest.mark.skipif(importlib.util.find_spec("qdrant_client") is None, reason="qdrant-client is optional")
def test_hybrid_qdrant_dense_uses_the_same_application_fusion(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    dense_service = KnowledgeIndexService(repository_root=root, index_root=Path("var/qdrant"), vector_store="qdrant")
    dense = dense_service.build(DeterministicEmbeddingProvider(dimensions=16, environment="test"))
    sparse_service = Bm25IndexService(repository_root=root)
    sparse = sparse_service.build()
    response = HybridKnowledgeRetriever(
        dense_retriever=TrainingKnowledgeRetriever(index_service=dense_service, provider=DeterministicEmbeddingProvider(dimensions=16, environment="test"), index_id=dense.manifest.index_id, vector_store="qdrant"),
        bm25_retriever=TrainingKnowledgeBm25Retriever(index_service=sparse_service, index_id=sparse.index_id),
    ).retrieve(KnowledgeRetrievalRequest(query="训练", top_k=4, language="zh-CN"))
    assert len(response.results) <= 4


class _Broken:
    def retrieve(self, request):
        raise RuntimeError("private failure text")


def test_hybrid_one_source_failure_falls_back_without_leaking_error(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    service = Bm25IndexService(repository_root=root)
    index = service.build()
    hybrid = HybridKnowledgeRetriever(dense_retriever=_Broken(), bm25_retriever=TrainingKnowledgeBm25Retriever(index_service=service, index_id=index.index_id))
    response = hybrid.retrieve(KnowledgeRetrievalRequest(query="训练", top_k=4, language="zh-CN"))
    assert "private failure text" not in response.model_dump_json()
    assert any("Dense retrieval was unavailable" in item for item in response.limitations)


def test_hybrid_both_fail_is_safe_error() -> None:
    hybrid = HybridKnowledgeRetriever(dense_retriever=_Broken(), bm25_retriever=_Broken())
    with pytest.raises(Exception, match="Hybrid knowledge retrieval is unavailable"):
        hybrid.retrieve(KnowledgeRetrievalRequest(query="test"))


def test_hybrid_trace_and_metrics_exclude_query(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    service = Bm25IndexService(repository_root=root)
    index = service.build()
    trace, metric = InMemoryTraceSink(), InMemoryMetricsSink()
    tracer = SafeTracer(FanoutTraceSink(trace, MetricsTraceSink(MetricsRecorder(metric))))
    hybrid = HybridKnowledgeRetriever(dense_retriever=_Broken(), bm25_retriever=TrainingKnowledgeBm25Retriever(index_service=service, index_id=index.index_id))
    with tracer.request(component="test", operation="request"):
        hybrid.retrieve(KnowledgeRetrievalRequest(query="secret query body", top_k=4, language="zh-CN"))
    span = next(item for item in trace.spans if item.operation == "hybrid_retrieval")
    assert span.fallback is True
    assert "secret query body" not in str(span.metadata)
    labels = {"component": "knowledge", "operation": "hybrid_retrieval", "status": "SUCCEEDED", "fallback": "true", "retrieval_strategy": "hybrid", "fusion_method": "rrf"}
    assert metric.counter("retrieval_query_count", labels=labels) == 1
