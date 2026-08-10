from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from planner_core.config import Settings
from server.agent.enums import AgentIntent
from server.agent.fallback import DeterministicCoachFallback
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.agent.schemas import AgentContext
from server.agent.trace import AgentTrace
from server.knowledge_retrieval.embeddings.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
)
from server.knowledge_retrieval.errors import KnowledgeEmbeddingProviderError
from server.provider_reliability import (
    ProviderFailureCategory,
    RetryPolicy,
    classify_provider_exception,
)
from server.observability.tracing import InMemoryTraceSink, SafeTracer
from tests.agent_tool_fakes import NOW


class StatusFailure(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeChatClient:
    def __init__(self, responses: list[object]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeEmbeddingResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}

    def json(self) -> dict[str, object]:
        return self.payload


class FakeEmbeddingClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.closed = False

    def post(self, _url: str, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


def chat_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "COACH_AGENT_ENABLED": True,
        "COACH_AGENT_API_KEY": "fictional-key",
        "COACH_AGENT_BASE_URL": "https://api.example.test/v1",
        "COACH_AGENT_MODEL": "fictional-model",
        "COACH_AGENT_MAX_RETRIES": 1,
        "COACH_AGENT_RETRY_INITIAL_BACKOFF_SECONDS": 0.25,
        "COACH_AGENT_RETRY_MAX_BACKOFF_SECONDS": 0.5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def embedding_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "KNOWLEDGE_EMBEDDING_ENABLED": True,
        "KNOWLEDGE_EMBEDDING_API_KEY": "fictional-key",
        "KNOWLEDGE_EMBEDDING_BASE_URL": "https://api.example.test/v1",
        "KNOWLEDGE_EMBEDDING_MODEL": "fictional-embedding",
        "KNOWLEDGE_EMBEDDING_DIMENSIONS": 3,
        "KNOWLEDGE_EMBEDDING_MAX_RETRIES": 1,
        "KNOWLEDGE_EMBEDDING_RETRY_INITIAL_BACKOFF_SECONDS": 0.25,
        "KNOWLEDGE_EMBEDDING_RETRY_MAX_BACKOFF_SECONDS": 0.5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def context() -> AgentContext:
    return AgentContext(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        user_id=1001,
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        current_time=NOW,
        timezone="Asia/Shanghai",
        runner_state={"overall_state": "UNKNOWN"},
    )


def chat_response(payload: dict[str, object]) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(payload), tool_calls=[]))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def embedding_payload(vector: list[float]) -> dict[str, object]:
    return {
        "object": "list",
        "data": [{"object": "embedding", "index": 0, "embedding": vector}],
        "model": "fictional-embedding",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }


@pytest.mark.parametrize(
    ("failure", "category", "retryable"),
    [
        (StatusFailure(429), ProviderFailureCategory.PROVIDER_RATE_LIMIT, True),
        (StatusFailure(500), ProviderFailureCategory.PROVIDER_SERVER_ERROR, True),
        (StatusFailure(400), ProviderFailureCategory.PROVIDER_BAD_REQUEST, False),
        (StatusFailure(401), ProviderFailureCategory.PROVIDER_AUTH_ERROR, False),
        (TimeoutError(), ProviderFailureCategory.PROVIDER_TIMEOUT, True),
        (ConnectionError(), ProviderFailureCategory.PROVIDER_CONNECTION_ERROR, True),
    ],
)
def test_failure_taxonomy_is_stable(failure: Exception, category: ProviderFailureCategory, retryable: bool) -> None:
    result = classify_provider_exception(failure)
    assert result.category == category
    assert result.retryable is retryable


def test_retry_policy_is_bounded_and_sleeper_is_injectable() -> None:
    policy = RetryPolicy(max_retries=2, initial_backoff_seconds=0.25, max_backoff_seconds=0.3)
    waits: list[float] = []
    assert policy.max_attempts == 3
    assert policy.wait(attempt=0, sleeper=waits.append) == 0.25
    assert policy.wait(attempt=1, sleeper=waits.append) == 0.3
    assert waits == [0.25, 0.3]


def test_chat_timeout_then_success_retries_with_safe_attempt_trace() -> None:
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    client = FakeChatClient(
        [
            httpx.ReadTimeout("fictional timeout", request=request),
            chat_response({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}),
        ]
    )
    waits: list[float] = []
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: client, sleeper=waits.append
    )
    trace = AgentTrace(request_id=context().request_id)

    output = gateway.generate(
        system_instructions="safe", user_message="fictional", context=context(), tools=[], trace=trace
    )

    assert output.answer == "safe"
    assert waits == [0.25]
    assert gateway.last_reliability.attempts == 2
    assert gateway.last_reliability.retried is True
    assert all("fictional timeout" not in event.model_dump_json() for event in trace.events)


@pytest.mark.parametrize("status", [429, 500])
def test_chat_retryable_http_failure_retries(status: int) -> None:
    client = FakeChatClient(
        [
            StatusFailure(status),
            chat_response({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}),
        ]
    )
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: client, sleeper=lambda _delay: None
    )
    gateway.generate(system_instructions="safe", user_message="fictional", context=context(), tools=[], trace=AgentTrace(request_id=context().request_id))
    assert len(client.completions.calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_chat_non_retryable_http_failure_does_not_retry(status: int) -> None:
    client = FakeChatClient([StatusFailure(status)])
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: client, sleeper=lambda _delay: None
    )
    with pytest.raises(AgentProviderError) as caught:
        gateway.generate(system_instructions="safe", user_message="fictional", context=context(), tools=[], trace=AgentTrace(request_id=context().request_id))
    assert len(client.completions.calls) == 1
    assert caught.value.category in {
        ProviderFailureCategory.PROVIDER_BAD_REQUEST,
        ProviderFailureCategory.PROVIDER_AUTH_ERROR,
    }


def test_chat_invalid_response_and_tool_protocol_do_not_retry() -> None:
    malformed = FakeChatClient([SimpleNamespace(choices=[], usage=None)])
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: malformed, sleeper=lambda _delay: None
    )
    with pytest.raises(AgentProviderError) as invalid:
        gateway.generate(system_instructions="safe", user_message="fictional", context=context(), tools=[], trace=AgentTrace(request_id=context().request_id))
    assert invalid.value.category == ProviderFailureCategory.PROVIDER_INVALID_RESPONSE
    assert len(malformed.completions.calls) == 1

    bad_call = SimpleNamespace(function=SimpleNamespace(arguments="{", name="safe_tool"))
    protocol = FakeChatClient([SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=None, tool_calls=[bad_call]))], usage=None)])
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: protocol, sleeper=lambda _delay: None
    )
    with pytest.raises(AgentProviderError) as invalid_tool:
        gateway.generate(system_instructions="safe", user_message="fictional", context=context(), tools=[], trace=AgentTrace(request_id=context().request_id))
    assert invalid_tool.value.category == ProviderFailureCategory.PROVIDER_TOOL_PROTOCOL_ERROR
    assert len(protocol.completions.calls) == 1


def test_embedding_timeout_then_success_retries_without_real_sleep() -> None:
    request = httpx.Request("POST", "https://api.example.test/v1/embeddings")
    client = FakeEmbeddingClient(
        [httpx.ReadTimeout("fictional timeout", request=request), FakeEmbeddingResponse(200, embedding_payload([1, 0, 0]))]
    )
    waits: list[float] = []
    provider = OpenAICompatibleEmbeddingProvider(
        embedding_settings(), client_factory=lambda _settings: client, sleeper=waits.append
    )
    result = provider.embed_query("fictional")
    assert result.dimensions == 3
    assert waits == [0.25]
    assert provider.last_reliability.attempts == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_embedding_non_retryable_status_does_not_retry(status: int) -> None:
    client = FakeEmbeddingClient([FakeEmbeddingResponse(status)])
    provider = OpenAICompatibleEmbeddingProvider(
        embedding_settings(), client_factory=lambda _settings: client, sleeper=lambda _delay: None
    )
    with pytest.raises(KnowledgeEmbeddingProviderError) as caught:
        provider.embed_query("fictional")
    assert len(client.calls) == 1
    assert caught.value.category in {
        ProviderFailureCategory.PROVIDER_BAD_REQUEST,
        ProviderFailureCategory.PROVIDER_AUTH_ERROR,
    }


def test_embedding_schema_count_dimension_and_nan_are_not_retried() -> None:
    count = FakeEmbeddingClient([FakeEmbeddingResponse(200, {**embedding_payload([1, 0, 0]), "data": []})])
    provider = OpenAICompatibleEmbeddingProvider(
        embedding_settings(), client_factory=lambda _settings: count, sleeper=lambda _delay: None
    )
    with pytest.raises(KnowledgeEmbeddingProviderError) as count_error:
        provider.embed_query("fictional")
    assert count_error.value.category == ProviderFailureCategory.PROVIDER_SCHEMA_ERROR
    assert len(count.calls) == 1

    dimension = FakeEmbeddingClient([FakeEmbeddingResponse(200, embedding_payload([1, 0]))])
    provider = OpenAICompatibleEmbeddingProvider(
        embedding_settings(), client_factory=lambda _settings: dimension, sleeper=lambda _delay: None
    )
    with pytest.raises(KnowledgeEmbeddingProviderError) as dimension_error:
        provider.embed_query("fictional")
    assert dimension_error.value.category == ProviderFailureCategory.PROVIDER_EMBEDDING_DIMENSION_ERROR

    nan = FakeEmbeddingClient([FakeEmbeddingResponse(200, embedding_payload([float("nan"), 0, 0]))])
    provider = OpenAICompatibleEmbeddingProvider(
        embedding_settings(), client_factory=lambda _settings: nan, sleeper=lambda _delay: None
    )
    with pytest.raises(KnowledgeEmbeddingProviderError) as nan_error:
        provider.embed_query("fictional")
    assert nan_error.value.category == ProviderFailureCategory.PROVIDER_SCHEMA_ERROR


def test_provider_span_contains_safe_attempt_metadata_only() -> None:
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    client = FakeChatClient(
        [
            httpx.ReadTimeout("fictional timeout", request=request),
            chat_response({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}),
        ]
    )
    gateway = OpenAICompatibleAgentGateway(
        chat_settings(), client_factory=lambda _settings, _url: client, sleeper=lambda _delay: None
    )
    sink = InMemoryTraceSink()
    tracer = SafeTracer(sink=sink)
    agent = GaitLogicCoachAgent(gateway=gateway, tracer=tracer)
    with tracer.request(component="test", operation="provider"):
        agent._call_model(request=SimpleNamespace(intent=AgentIntent.EXPLAIN_RUNNER_STATE, message="private question"), context=context(), trace=AgentTrace(request_id=context().request_id))
    provider_span = next(item for item in sink.spans if item.component == "provider")
    assert provider_span.metadata["provider_kind"] == "chat"
    assert provider_span.metadata["attempt"] == 2
    assert provider_span.metadata["max_attempts"] == 2
    assert provider_span.metadata["retried"] is True
    assert "private question" not in provider_span.metadata.values()


def test_fallback_retains_today_canonical_facts_after_provider_failure() -> None:
    today = context().model_copy(
        update={
            "intent": AgentIntent.TODAY_RECOMMENDATION,
            "today_workout": {"workout_status": "PLANNED"},
            "today_evaluation": {
                "data_status": "AVAILABLE",
                "decision": "passed_with_notice",
                "risk_level": "MODERATE",
                "warnings": [{"code": "SERVER_WARNING", "message": "safe"}],
                "limitations": [],
            },
            "data_quality": {"data_status": "AVAILABLE"},
        }
    )
    fallback = DeterministicCoachFallback().build(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        message="fictional",
        context=today,
    )
    assert fallback.today_recommendation is not None
    assert fallback.today_recommendation.decision == "PROCEED_WITH_CAUTION"
    assert [warning.code for warning in fallback.warnings] == ["SERVER_WARNING"]
    assert today.today_workout == {"workout_status": "PLANNED"}
