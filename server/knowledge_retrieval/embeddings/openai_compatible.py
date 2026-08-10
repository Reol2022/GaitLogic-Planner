from __future__ import annotations

from collections.abc import Callable
from time import sleep
from typing import Any, Literal

import httpx
from pydantic import Field, ValidationError, field_validator

from planner_core.config import Settings
from server.knowledge_retrieval.embeddings.deterministic import (
    MAX_QUERY_CHARS,
    MAX_TEXT_CHARS,
    normalize_vector,
)
from server.knowledge_retrieval.embeddings.schemas import (
    EmbeddingBatch,
    EmbeddingUsage,
    EmbeddingVector,
    validate_vector,
)
from server.knowledge_retrieval.embeddings.security import (
    validate_embedding_base_url,
)
from server.knowledge_retrieval.errors import (
    KnowledgeEmbeddingConfigurationError,
    KnowledgeEmbeddingError,
    KnowledgeEmbeddingProviderError,
)
from server.knowledge_retrieval.schemas import StrictModel
from server.provider_reliability import (
    ProviderCallReliability,
    ProviderFailureCategory,
    RetryPolicy,
    classify_provider_exception,
)


class _ProviderEmbeddingItem(StrictModel):
    object: Literal["embedding"]
    index: int = Field(ge=0)
    embedding: list[float]

    @field_validator("embedding")
    @classmethod
    def vector_is_valid(cls, value: list[float]) -> list[float]:
        return validate_vector(value)


class _ProviderUsage(StrictModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int = Field(ge=0)


class _ProviderResponse(StrictModel):
    object: Literal["list"]
    data: list[_ProviderEmbeddingItem]
    model: str
    usage: _ProviderUsage | None = None


class _StatusFailure(Exception):
    """Minimal status carrier for shared error classification."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class OpenAICompatibleEmbeddingProvider:
    provider_name = "openai_compatible"
    normalized = True

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[Settings], Any] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if not settings.knowledge_embedding_enabled:
            raise KnowledgeEmbeddingConfigurationError(
                "Knowledge embedding provider is disabled."
            )
        if not settings.knowledge_embedding_api_key:
            raise KnowledgeEmbeddingConfigurationError(
                "Knowledge embedding API key is not configured."
            )
        allow_local = (
            settings.app_env.lower() == "development"
            and settings.knowledge_embedding_allow_local_provider_in_development
        )
        self.base_url = validate_embedding_base_url(
            settings.knowledge_embedding_base_url,
            allow_local_development=allow_local,
        )
        self.settings = settings
        self.model_name = settings.knowledge_embedding_model
        self.dimensions = settings.knowledge_embedding_dimensions or 0
        self.max_batch_size = settings.knowledge_embedding_batch_size
        self._client_factory = client_factory or self._default_client
        self._sleeper = sleeper
        self._client: Any | None = None
        self.last_reliability = ProviderCallReliability(
            attempts=0,
            max_attempts=settings.knowledge_embedding_max_retries + 1,
            failure_category=None,
            retried=False,
            final_status="NOT_CALLED",
        )

    @staticmethod
    def _default_client(settings: Settings) -> httpx.Client:
        timeout = httpx.Timeout(
            settings.knowledge_embedding_total_timeout_seconds,
            connect=settings.knowledge_embedding_connect_timeout_seconds,
            read=settings.knowledge_embedding_read_timeout_seconds,
        )
        return httpx.Client(timeout=timeout, follow_redirects=False)

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(self.settings)
        return self._client

    @staticmethod
    def _validate_text(text: str, *, limit: int) -> str:
        value = text.strip()
        if not value:
            raise KnowledgeEmbeddingError("Embedding input cannot be empty.")
        if len(value) > limit:
            raise KnowledgeEmbeddingError("Embedding input exceeds the length limit.")
        return value

    def _retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.settings.knowledge_embedding_max_retries,
            initial_backoff_seconds=self.settings.knowledge_embedding_retry_initial_backoff_seconds,
            max_backoff_seconds=self.settings.knowledge_embedding_retry_max_backoff_seconds,
        )

    def _discard_client(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None

    def _request(self, texts: list[str]) -> tuple[list[list[float]], EmbeddingUsage]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "input": texts,
            "encoding_format": "float",
        }
        if self.settings.knowledge_embedding_dimensions is not None:
            payload["dimensions"] = self.settings.knowledge_embedding_dimensions
        headers = {
            "Authorization": f"Bearer {self.settings.knowledge_embedding_api_key}",
            "Content-Type": "application/json",
        }
        response: Any | None = None
        policy = self._retry_policy()
        for attempt in range(policy.max_attempts):
            try:
                response = self.client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
            except Exception as exc:
                failure = classify_provider_exception(exc)
                if policy.can_retry(attempt=attempt, failure=failure):
                    self._discard_client()
                    policy.wait(attempt=attempt, sleeper=self._sleeper)
                    continue
                self.last_reliability = ProviderCallReliability(
                    attempts=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=failure.category,
                    retried=attempt > 0,
                    final_status="FAILED",
                )
                raise KnowledgeEmbeddingProviderError(
                    "Embedding provider is unavailable.",
                    category=failure.category,
                ) from exc
            status = int(response.status_code)
            if 200 <= status < 300:
                break
            failure = classify_provider_exception(
                _StatusFailure(status)
            )
            if policy.can_retry(attempt=attempt, failure=failure):
                policy.wait(attempt=attempt, sleeper=self._sleeper)
                continue
            self.last_reliability = ProviderCallReliability(
                attempts=attempt + 1,
                max_attempts=policy.max_attempts,
                failure_category=failure.category,
                retried=attempt > 0,
                final_status="FAILED",
            )
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider rejected the request.",
                category=failure.category,
            )
        if response is None or not (200 <= int(response.status_code) < 300):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider is unavailable.",
                category=ProviderFailureCategory.PROVIDER_UNKNOWN_ERROR,
            )
        try:
            parsed = _ProviderResponse.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as exc:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned an invalid response.",
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            ) from exc
        if len(parsed.data) != len(texts):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned an unexpected vector count.",
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            )
        if parsed.model != self.model_name:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider response model does not match configuration.",
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            )
        ordered = sorted(parsed.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(texts))):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned invalid vector ordering.",
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            )
        raw_dimensions = len(ordered[0].embedding) if ordered else 0
        if raw_dimensions == 0 or any(
            len(item.embedding) != raw_dimensions for item in ordered
        ):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned inconsistent dimensions.",
                category=ProviderFailureCategory.PROVIDER_EMBEDDING_DIMENSION_ERROR,
            )
        configured = self.settings.knowledge_embedding_dimensions
        if configured is not None and raw_dimensions != configured:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider dimensions do not match configuration.",
                category=ProviderFailureCategory.PROVIDER_EMBEDDING_DIMENSION_ERROR,
            )
        if self.dimensions not in {0, raw_dimensions}:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider dimensions changed during this session.",
                category=ProviderFailureCategory.PROVIDER_EMBEDDING_DIMENSION_ERROR,
            )
        try:
            vectors = [normalize_vector(item.embedding) for item in ordered]
        except KnowledgeEmbeddingError as exc:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned an invalid vector.",
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            ) from exc
        self.dimensions = raw_dimensions
        usage = EmbeddingUsage(
            input_count=len(texts),
            prompt_tokens=parsed.usage.prompt_tokens if parsed.usage else None,
            total_tokens=parsed.usage.total_tokens if parsed.usage else None,
        )
        self.last_reliability = ProviderCallReliability(
            attempts=attempt + 1,
            max_attempts=policy.max_attempts,
            failure_category=None,
            retried=attempt > 0,
            final_status="SUCCEEDED",
        )
        return vectors, usage

    def embed_documents(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            raise KnowledgeEmbeddingError("Embedding document batch cannot be empty.")
        if len(texts) > self.max_batch_size:
            raise KnowledgeEmbeddingError("Embedding document batch is too large.")
        values = [
            self._validate_text(text, limit=MAX_TEXT_CHARS)
            for text in texts
        ]
        vectors, usage = self._request(values)
        return EmbeddingBatch(
            vectors=vectors,
            dimensions=self.dimensions,
            provider=self.provider_name,
            model=self.model_name,
            normalized=True,
            usage=usage,
        )

    def embed_query(self, text: str) -> EmbeddingVector:
        value = self._validate_text(text, limit=MAX_QUERY_CHARS)
        vectors, usage = self._request([value])
        return EmbeddingVector(
            vector=vectors[0],
            dimensions=self.dimensions,
            provider=self.provider_name,
            model=self.model_name,
            normalized=True,
            usage=usage,
        )

    def close(self) -> None:
        self._discard_client()
