from __future__ import annotations

import inspect
import math

import httpx
import pytest
from pydantic import ValidationError

from planner_core.config import Settings
from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.embeddings.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
)
from server.knowledge_retrieval.embeddings.schemas import (
    EmbeddingBatch,
    EmbeddingVector,
)
from server.knowledge_retrieval.embeddings.security import (
    validate_embedding_base_url,
)
from server.knowledge_retrieval.errors import (
    KnowledgeEmbeddingConfigurationError,
    KnowledgeEmbeddingError,
    KnowledgeEmbeddingProviderError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.closed = False

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


def provider_payload(vectors: list[list[float]]) -> dict:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": index, "embedding": vector}
            for index, vector in enumerate(vectors)
        ],
        "model": "test-embedding",
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }


def enabled_settings(**overrides) -> Settings:
    values = {
        "KNOWLEDGE_EMBEDDING_ENABLED": True,
        "KNOWLEDGE_EMBEDDING_API_KEY": "fictional-test-key",
        "KNOWLEDGE_EMBEDDING_BASE_URL": "https://api.example.test/v1",
        "KNOWLEDGE_EMBEDDING_MODEL": "test-embedding",
        "KNOWLEDGE_EMBEDDING_DIMENSIONS": 3,
        "KNOWLEDGE_EMBEDDING_BATCH_SIZE": 4,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_deterministic_embedding_is_stable_normalized_and_chinese_safe() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=32)
    first = provider.embed_documents(["疲劳较高时调整训练", "second"])
    second = provider.embed_documents(["疲劳较高时调整训练", "second"])
    assert first.vectors == second.vectors
    assert len(first.vectors) == 2
    assert all(len(vector) == 32 for vector in first.vectors)
    assert all(
        math.isclose(sum(value * value for value in vector), 1.0)
        for vector in first.vectors
    )


def test_deterministic_rejects_empty_large_batch_and_production() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=16, max_batch_size=1)
    with pytest.raises(KnowledgeEmbeddingError):
        provider.embed_documents([])
    with pytest.raises(KnowledgeEmbeddingError):
        provider.embed_documents(["one", "two"])
    with pytest.raises(KnowledgeEmbeddingError):
        provider.embed_query(" ")
    with pytest.raises(KnowledgeEmbeddingConfigurationError):
        DeterministicEmbeddingProvider(environment="production")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_embedding_schema_rejects_non_finite_vectors(value: float) -> None:
    with pytest.raises(ValidationError):
        EmbeddingVector(
            vector=[value],
            dimensions=1,
            provider="test",
            model="test",
            normalized=False,
        )


def test_embedding_schema_rejects_dimension_changes() -> None:
    with pytest.raises(ValidationError):
        EmbeddingBatch(
            vectors=[[1.0, 0.0], [1.0]],
            dimensions=2,
            provider="test",
            model="test",
            normalized=False,
        )


def test_openai_provider_is_disabled_by_default() -> None:
    with pytest.raises(KnowledgeEmbeddingConfigurationError, match="disabled"):
        OpenAICompatibleEmbeddingProvider(Settings(_env_file=None))


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test/v1",
        "http://localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
        "http://10.0.0.1/v1",
        "http://169.254.169.254/latest",
        "https://user:pass@example.test/v1",
        "https://example.test/v1?redirect=http://127.0.0.1",
    ],
)
def test_embedding_url_security_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(KnowledgeEmbeddingConfigurationError):
        validate_embedding_base_url(url)


def test_embedding_url_allows_explicit_local_development() -> None:
    assert (
        validate_embedding_base_url(
            "http://127.0.0.1:8765/v1",
            allow_local_development=True,
        )
        == "http://127.0.0.1:8765/v1"
    )


def test_openai_provider_preserves_order_and_normalizes() -> None:
    client = FakeClient(
        [FakeResponse(200, provider_payload([[3, 0, 0], [0, 4, 0]]))]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: client,
    )
    batch = provider.embed_documents(["first", "second"])
    assert batch.vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert client.calls[0]["json"]["input"] == ["first", "second"]
    assert client.calls[0]["json"]["model"] == "test-embedding"
    provider.close()
    assert client.closed is True


def test_openai_provider_accepts_typed_completion_token_usage() -> None:
    payload = provider_payload([[1, 0, 0]])
    payload["usage"]["completion_tokens"] = 0
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: FakeClient([FakeResponse(200, payload)]),
    )

    result = provider.embed_query("test")

    assert result.usage.prompt_tokens == 3
    assert result.usage.total_tokens == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("completion_tokens", -1),
        ("provider_specific_tokens", 0),
    ],
)
def test_openai_provider_rejects_invalid_or_unknown_usage_fields(
    field: str,
    value: int,
) -> None:
    payload = provider_payload([[1, 0, 0]])
    payload["usage"][field] = value
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: FakeClient([FakeResponse(200, payload)]),
    )

    with pytest.raises(KnowledgeEmbeddingProviderError, match="invalid response"):
        provider.embed_query("test")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_status_retries_once(status: int) -> None:
    client = FakeClient(
        [
            FakeResponse(status),
            FakeResponse(200, provider_payload([[1, 0, 0]])),
        ]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: client,
    )
    provider.embed_query("test")
    assert len(client.calls) == 2


def test_timeout_retries_once() -> None:
    request = httpx.Request("POST", "https://api.example.test/v1/embeddings")
    client = FakeClient(
        [
            httpx.ReadTimeout("timeout", request=request),
            FakeResponse(200, provider_payload([[1, 0, 0]])),
        ]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: client,
    )
    provider.embed_query("test")
    assert len(client.calls) == 2


def test_transport_connection_error_retries_once() -> None:
    request = httpx.Request("POST", "https://api.example.test/v1/embeddings")
    failed_client = FakeClient(
        [httpx.ConnectError("connection failed", request=request)]
    )
    recovered_client = FakeClient(
        [FakeResponse(200, provider_payload([[1, 0, 0]]))]
    )
    clients = [failed_client, recovered_client]
    factory_calls = 0

    def factory(settings: Settings) -> FakeClient:
        nonlocal factory_calls
        del settings
        client = clients[factory_calls]
        factory_calls += 1
        return client

    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=factory,
    )
    provider.embed_query("test")
    assert factory_calls == 2
    assert failed_client.closed is True
    assert len(failed_client.calls) == 1
    assert len(recovered_client.calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403])
def test_non_retryable_status_is_not_retried(status: int) -> None:
    client = FakeClient([FakeResponse(status)])
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: client,
    )
    with pytest.raises(KnowledgeEmbeddingProviderError):
        provider.embed_query("test")
    assert len(client.calls) == 1


def test_provider_rejects_count_and_dimension_mismatch() -> None:
    count_client = FakeClient(
        [FakeResponse(200, provider_payload([[1, 0, 0]]))]
    )
    count_provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: count_client,
    )
    with pytest.raises(KnowledgeEmbeddingProviderError, match="count"):
        count_provider.embed_documents(["one", "two"])

    dimension_client = FakeClient(
        [FakeResponse(200, provider_payload([[1, 0]]))]
    )
    dimension_provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: dimension_client,
    )
    with pytest.raises(KnowledgeEmbeddingProviderError, match="dimensions"):
        dimension_provider.embed_query("one")


def test_provider_rejects_response_model_mismatch() -> None:
    payload = provider_payload([[1, 0, 0]])
    payload["model"] = "different-model"
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: FakeClient([FakeResponse(200, payload)]),
    )
    with pytest.raises(KnowledgeEmbeddingProviderError, match="model"):
        provider.embed_query("one")


def test_redirects_are_disabled_and_logs_do_not_contain_key_or_vector(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert "follow_redirects=False" in inspect.getsource(
        OpenAICompatibleEmbeddingProvider._default_client
    )
    client = FakeClient(
        [FakeResponse(200, provider_payload([[1, 0, 0]]))]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        enabled_settings(),
        client_factory=lambda settings: client,
    )
    provider.embed_query("private fictional query")
    assert "fictional-test-key" not in caplog.text
    assert "[1.0, 0.0, 0.0]" not in caplog.text
