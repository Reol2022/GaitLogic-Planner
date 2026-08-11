from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from planner_core.config import Settings
from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.reranking.base import RerankCandidate, RerankResult
from server.knowledge_retrieval.reranking.retriever import RerankingKnowledgeRetriever
from server.knowledge_retrieval.reranking.siliconflow import SiliconFlowReranker
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer


ROOT = Path(__file__).resolve().parents[1]


class _Response:
    def __init__(self, status_code: int, data: object) -> None:
        self.status_code, self._data = status_code, data

    def json(self) -> object:
        return self._data


class _Client:
    def __init__(self, values: list[object]) -> None:
        self.values, self.calls = values, []

    def post(self, url, *, headers, json):
        self.calls.append((url, headers, json))
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _settings(**values: object) -> Settings:
    env = {
        "KNOWLEDGE_RERANKER_ENABLED": True,
        "KNOWLEDGE_RERANKER_API_KEY": "test-only-secret",
        "KNOWLEDGE_RERANKER_BASE_URL": "https://api.siliconflow.cn/v1",
        "KNOWLEDGE_RERANKER_MAX_RETRIES": 1,
    }
    env.update(values)
    return Settings(_env_file=None, **env)


def _candidates() -> list[RerankCandidate]:
    return [RerankCandidate("chunk-a", "public fixture A"), RerankCandidate("chunk-b", "public fixture B")]


def test_siliconflow_request_is_index_only_and_never_accepts_provider_documents() -> None:
    client = _Client([_Response(200, {"results": [{"index": 1, "relevance_score": 0.9}]})])
    provider = SiliconFlowReranker(_settings(), client_factory=lambda _: client)
    result = provider.rerank(query="public fixture query", candidates=_candidates(), top_n=1)
    assert result == [RerankResult(index=1, relevance_score=0.9)]
    _, headers, body = client.calls[0]
    assert body["return_documents"] is False
    assert body["documents"] == ["public fixture A", "public fixture B"]
    assert "test-only-secret" not in str(body)
    assert headers["Authorization"] == "Bearer test-only-secret"


def test_siliconflow_discards_provider_metadata_and_document_echoes() -> None:
    client = _Client([
        _Response(
            200,
            {
                "id": "provider-request-id",
                "meta": {"usage": "provider-owned"},
                "results": [
                    {
                        "index": 1,
                        "relevance_score": 0.9,
                        "document": "provider-owned text that must be discarded",
                    }
                ],
            },
        )
    ])
    provider = SiliconFlowReranker(_settings(), client_factory=lambda _: client)

    result = provider.rerank(query="public fixture query", candidates=_candidates(), top_n=1)

    assert result == [RerankResult(index=1, relevance_score=0.9)]
    assert "provider-owned" not in repr(result)


def test_siliconflow_reranker_reuses_a_siliconflow_embedding_secret() -> None:
    settings = _settings(
        KNOWLEDGE_RERANKER_API_KEY=None,
        KNOWLEDGE_EMBEDDING_API_KEY="test-only-embedding-secret",
        KNOWLEDGE_EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1",
    )
    client = _Client([_Response(200, {"results": [{"index": 0, "relevance_score": 0.9}]})])
    SiliconFlowReranker(settings, client_factory=lambda _: client).rerank(
        query="fixture", candidates=_candidates(), top_n=1
    )
    assert client.calls[0][1]["Authorization"] == "Bearer test-only-embedding-secret"


@pytest.mark.parametrize("payload", [
    {"results": [{"index": 2, "relevance_score": 0.1}]},
    {"results": [{"index": 0, "relevance_score": 0.1}, {"index": 0, "relevance_score": 0.2}]},
    {"results": [{"index": 0, "relevance_score": float("nan")} ]},
    {"results": []},
])
def test_siliconflow_rejects_invalid_indices_and_scores(payload: object) -> None:
    provider = SiliconFlowReranker(_settings(), client_factory=lambda _: _Client([_Response(200, payload)]))
    with pytest.raises(Exception, match="invalid"):
        provider.rerank(query="fixture", candidates=_candidates(), top_n=2)


def test_siliconflow_retries_429_but_not_auth_error() -> None:
    retried = _Client([_Response(429, {}), _Response(200, {"results": [{"index": 0, "relevance_score": 0.1}]})])
    provider = SiliconFlowReranker(_settings(), client_factory=lambda _: retried, sleeper=lambda _: None)
    provider.rerank(query="fixture", candidates=_candidates(), top_n=1)
    assert len(retried.calls) == 2 and provider.last_reliability.retried is True
    denied = _Client([_Response(401, {})])
    provider = SiliconFlowReranker(_settings(), client_factory=lambda _: denied, sleeper=lambda _: None)
    with pytest.raises(Exception):
        provider.rerank(query="fixture", candidates=_candidates(), top_n=1)
    assert len(denied.calls) == 1


class _FailingReranker:
    provider_kind = "fake"
    model_family = "test"
    instruction_version = "test"

    def __init__(self) -> None:
        from server.provider_reliability import ProviderCallReliability
        self.last_reliability = ProviderCallReliability(1, 1, None, False, "FAILED")

    def rerank(self, **kwargs):
        del kwargs
        raise RuntimeError("private provider body")


def test_reranker_failure_returns_hybrid_order_without_leaking_provider_body(tmp_path: Path) -> None:
    import shutil
    (tmp_path / "knowledge/manifests").mkdir(parents=True)
    shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", tmp_path / "knowledge/manifests/corpus-v1.json")
    dense_service = KnowledgeIndexService(repository_root=tmp_path, index_root=Path("var/dense"))
    dense_index = dense_service.build(DeterministicEmbeddingProvider(dimensions=32, environment="test"))
    bm25_service = Bm25IndexService(repository_root=tmp_path)
    bm25_index = bm25_service.build()
    retriever = RerankingKnowledgeRetriever(
        dense_retriever=TrainingKnowledgeRetriever(index_service=dense_service, provider=DeterministicEmbeddingProvider(dimensions=32, environment="test"), index_id=dense_index.manifest.index_id),
        bm25_retriever=TrainingKnowledgeBm25Retriever(index_service=bm25_service, index_id=bm25_index.index_id),
        reranker=_FailingReranker(), corpus_manifest_path=dense_service.corpus_manifest_path,
    )
    trace, metric = InMemoryTraceSink(), InMemoryMetricsSink()
    tracer = SafeTracer(FanoutTraceSink(trace, MetricsTraceSink(MetricsRecorder(metric))))
    with tracer.request(component="test", operation="request"):
        response = retriever.retrieve(KnowledgeRetrievalRequest(query="训练恢复", top_k=4, language="zh-CN"))
    assert response.results and "private provider body" not in response.model_dump_json()
    assert any("stable Hybrid RRF" in item for item in response.limitations)
    span = next(item for item in trace.spans if item.component == "knowledge" and item.operation == "rerank")
    assert span.fallback is True and "训练恢复" not in str(span.metadata)
    assert metric.counter("reranker_fallback_count") == 1
