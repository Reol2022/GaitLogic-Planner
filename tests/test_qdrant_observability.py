from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.observability.metrics import (
    InMemoryMetricsSink,
    MetricsRecorder,
    MetricsTraceSink,
)
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer
from tests.knowledge_index_helpers import prepare_repository


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("qdrant_client") is None,
    reason="qdrant-client is an optional dependency",
)


def test_qdrant_search_emits_safe_trace_and_low_cardinality_metrics(
    tmp_path: Path,
) -> None:
    service = type(prepare_repository(tmp_path))(
        repository_root=tmp_path,
        vector_store="qdrant",
    )
    build = service.build(DeterministicEmbeddingProvider(dimensions=16))
    trace_sink = InMemoryTraceSink()
    metric_sink = InMemoryMetricsSink()
    tracer = SafeTracer(
        FanoutTraceSink(
            trace_sink,
            MetricsTraceSink(MetricsRecorder(metric_sink)),
        )
    )
    retriever = TrainingKnowledgeRetriever(
        index_service=service,
        provider=DeterministicEmbeddingProvider(dimensions=16),
        index_id=build.manifest.index_id,
        vector_store="qdrant",
    )

    with tracer.request(component="test", operation="request"):
        retriever.retrieve(KnowledgeRetrievalRequest(query="private query", top_k=1))

    vector_span = next(
        item
        for item in trace_sink.spans
        if item.component == "knowledge" and item.operation == "vector_search"
    )
    assert vector_span.metadata["vector_store"] == "qdrant_dense_v1"
    assert vector_span.metadata["index_id"] == build.manifest.index_id
    assert "private query" not in str(vector_span.metadata)
    labels = {
        "component": "knowledge",
        "operation": "vector_search",
        "status": "SUCCEEDED",
        "fallback": "false",
        "vector_store": "qdrant_dense_v1",
    }
    assert metric_sink.counter("vector_store_query_count", labels=labels) == 1
