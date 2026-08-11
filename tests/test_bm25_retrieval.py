from __future__ import annotations

from pathlib import Path
import json
import shutil

import pytest

from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.sparse.bm25 import BM25Analyzer
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer


ROOT = Path(__file__).resolve().parents[1]


def service_for(tmp_path: Path) -> Bm25IndexService:
    manifests = tmp_path / "knowledge/manifests"
    manifests.mkdir(parents=True)
    shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", manifests / "corpus-v1.json")
    return Bm25IndexService(repository_root=tmp_path)


def test_bm25_build_search_and_deterministic_order(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    retriever = TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id)
    request = KnowledgeRetrievalRequest(query="threshold training session", top_k=4, language="en-US")
    first = retriever.retrieve(request)
    second = retriever.retrieve(request)
    assert first.model_dump() == second.model_dump()
    assert len(first.results) <= 4
    assert first.index_id == manifest.index_id


def test_mixed_language_numeric_and_abbreviation_tokenization_is_stable() -> None:
    tokens = BM25Analyzer.tokenize("RPE 7，10km 阈值训练 / Zone-2")
    assert "rpe" in tokens
    assert "10km" in tokens
    assert "zone-2" in tokens
    assert "阈" in tokens and "阈值" in tokens


def test_bm25_filter_semantics_category_or_tags_and_language_exact(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    response = TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id).retrieve(
        KnowledgeRetrievalRequest(query="训练", top_k=10, tags=["recovery"], language="zh-CN")
    )
    assert all("recovery" in item.tags and item.relative_path and item.category for item in response.results)
    assert not TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id).retrieve(
        KnowledgeRetrievalRequest(query="training", top_k=4, language="en-US")
    ).results


def test_bm25_stale_corpus_is_rejected(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    path = tmp_path / "knowledge/manifests/corpus-v1.json"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeIndexError, match="stale"):
        service.validate(manifest.index_id)


def test_bm25_stale_analyzer_is_rejected(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    path = tmp_path / "var/knowledge_bm25_indexes" / manifest.index_id / "bm25-index.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["manifest"]["analyzer_version"] = "obsolete-analyzer"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KnowledgeIndexError, match="analyzer"):
        service.validate(manifest.index_id)


def test_bm25_empty_result_is_safe(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    response = TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id).retrieve(
        KnowledgeRetrievalRequest(query="zzzz-no-corpus-match", top_k=4, language="zh-CN")
    )
    assert response.results == []
    assert response.limitations == ["No knowledge chunks matched the requested filters."]


def test_bm25_trace_and_metrics_are_safe_and_low_cardinality(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    manifest = service.build()
    trace_sink, metric_sink = InMemoryTraceSink(), InMemoryMetricsSink()
    tracer = SafeTracer(FanoutTraceSink(trace_sink, MetricsTraceSink(MetricsRecorder(metric_sink))))
    retriever = TrainingKnowledgeBm25Retriever(index_service=service, index_id=manifest.index_id)
    with tracer.request(component="test", operation="request"):
        retriever.retrieve(KnowledgeRetrievalRequest(query="private runner message", top_k=1, language="zh-CN"))
    span = next(item for item in trace_sink.spans if item.operation == "sparse_search")
    assert span.metadata["retrieval_strategy"] == "bm25"
    assert "private runner message" not in str(span.metadata)
    labels = {"component": "knowledge", "operation": "sparse_search", "status": "SUCCEEDED", "fallback": "false", "retrieval_strategy": "bm25"}
    assert metric_sink.counter("retrieval_query_count", labels=labels) == 1
