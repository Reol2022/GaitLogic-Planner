from __future__ import annotations

from collections.abc import Callable
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


class OpenAICompatibleEmbeddingProvider:
    provider_name = "openai_compatible"
    normalized = True

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[Settings], Any] | None = None,
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
        self._client: Any | None = None

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

    @staticmethod
    def _retryable_exception(exc: Exception) -> bool:
        return isinstance(
            exc,
            (
                httpx.TimeoutException,
                TimeoutError,
            ),
        )

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
        for attempt in range(2):
            try:
                response = self.client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
            except Exception as exc:
                if attempt == 0 and self._retryable_exception(exc):
                    continue
                raise KnowledgeEmbeddingProviderError(
                    "Embedding provider is unavailable."
                ) from exc
            status = int(response.status_code)
            if 200 <= status < 300:
                break
            if attempt == 0 and (status == 429 or status >= 500):
                continue
            raise KnowledgeEmbeddingProviderError(
                f"Embedding provider rejected the request with status {status}."
            )
        if response is None or not (200 <= int(response.status_code) < 300):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider is unavailable."
            )
        try:
            parsed = _ProviderResponse.model_validate(response.json())
        except (ValidationError, ValueError, TypeError) as exc:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned an invalid response."
            ) from exc
        if len(parsed.data) != len(texts):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned an unexpected vector count."
            )
        if parsed.model != self.model_name:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider response model does not match configuration."
            )
        ordered = sorted(parsed.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(texts))):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned invalid vector ordering."
            )
        raw_dimensions = len(ordered[0].embedding) if ordered else 0
        if raw_dimensions == 0 or any(
            len(item.embedding) != raw_dimensions for item in ordered
        ):
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider returned inconsistent dimensions."
            )
        configured = self.settings.knowledge_embedding_dimensions
        if configured is not None and raw_dimensions != configured:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider dimensions do not match configuration."
            )
        if self.dimensions not in {0, raw_dimensions}:
            raise KnowledgeEmbeddingProviderError(
                "Embedding provider dimensions changed during this session."
            )
        self.dimensions = raw_dimensions
        vectors = [normalize_vector(item.embedding) for item in ordered]
        usage = EmbeddingUsage(
            input_count=len(texts),
            prompt_tokens=parsed.usage.prompt_tokens if parsed.usage else None,
            total_tokens=parsed.usage.total_tokens if parsed.usage else None,
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
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None
