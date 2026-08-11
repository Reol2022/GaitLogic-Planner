"""SiliconFlow's documented ``POST /v1/rerank`` adapter.

The adapter deliberately accepts and returns only local candidate positions.  It
never accepts Provider-provided documents, titles, sources, or metadata.
"""

from __future__ import annotations

from collections.abc import Callable
from math import isfinite
from time import sleep
from typing import Any, Literal

import httpx
from pydantic import Field, ValidationError

from planner_core.config import Settings
from server.knowledge_retrieval.embeddings.security import validate_embedding_base_url
from server.knowledge_retrieval.reranking.base import RerankCandidate, RerankResult
from server.knowledge_retrieval.reranking.errors import KnowledgeRerankerError
from server.knowledge_retrieval.schemas import StrictModel
from server.provider_reliability import (
    ProviderCallReliability,
    ProviderFailureCategory,
    RetryPolicy,
    classify_provider_exception,
)


RERANK_INSTRUCTION = (
    "Rank candidate endurance-running training knowledge by how directly it "
    "answers the query. Prefer directly relevant guidance over shared keywords."
)
RERANK_INSTRUCTION_VERSION = "gaitlogic_rerank_v1"


class _ResponseItem(StrictModel):
    index: int = Field(ge=0)
    relevance_score: float


class _Response(StrictModel):
    results: list[_ResponseItem]


class _StatusFailure(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class SiliconFlowReranker:
    provider_kind = "siliconflow"
    model_family = "qwen3-reranker"
    instruction_version = RERANK_INSTRUCTION_VERSION

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[Settings], Any] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if not settings.knowledge_reranker_enabled:
            raise KnowledgeRerankerError("Reranker is disabled.")
        if not settings.knowledge_reranker_effective_api_key:
            raise KnowledgeRerankerError("Reranker API key is not configured.")
        allow_local = settings.app_env.lower() == "development" and settings.knowledge_embedding_allow_local_provider_in_development
        self.base_url = validate_embedding_base_url(
            settings.knowledge_reranker_base_url,
            allow_local_development=allow_local,
        )
        self.settings = settings
        self.model_name = settings.knowledge_reranker_model
        self._client_factory = client_factory or self._default_client
        self._sleeper = sleeper
        self._client: Any | None = None
        self.last_reliability = ProviderCallReliability(0, settings.knowledge_reranker_max_retries + 1, None, False, "NOT_CALLED")

    @staticmethod
    def _default_client(settings: Settings) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(
                settings.knowledge_reranker_total_timeout_seconds,
                connect=settings.knowledge_reranker_connect_timeout_seconds,
                read=settings.knowledge_reranker_read_timeout_seconds,
            ),
            follow_redirects=False,
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(self.settings)
        return self._client

    def _discard_client(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None

    def _policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.settings.knowledge_reranker_max_retries,
            initial_backoff_seconds=self.settings.knowledge_reranker_retry_initial_backoff_seconds,
            max_backoff_seconds=self.settings.knowledge_reranker_retry_max_backoff_seconds,
        )

    def _fail(self, *, attempt: int, policy: RetryPolicy, category: ProviderFailureCategory, message: str, cause: Exception | None = None) -> None:
        self.last_reliability = ProviderCallReliability(attempt + 1, policy.max_attempts, category, attempt > 0, "FAILED")
        error = KnowledgeRerankerError(message, category=category)
        if cause is not None:
            raise error from cause
        raise error

    @staticmethod
    def _validate_results(raw: _Response, *, candidate_count: int, top_n: int) -> list[RerankResult]:
        if len(raw.results) != top_n:
            raise KnowledgeRerankerError("Reranker returned an invalid result count.", category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR)
        seen: set[int] = set()
        output: list[RerankResult] = []
        for item in raw.results:
            if item.index in seen or item.index >= candidate_count or not isfinite(item.relevance_score):
                raise KnowledgeRerankerError("Reranker returned invalid candidate indices or scores.", category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR)
            seen.add(item.index)
            output.append(RerankResult(index=item.index, relevance_score=item.relevance_score))
        return sorted(output, key=lambda item: (-item.relevance_score, item.index))

    @staticmethod
    def _response_for_validation(payload: Any) -> dict[str, Any]:
        """Discard all Provider-owned response fields before strict validation.

        SiliconFlow's compatible endpoint includes request metadata at the root
        and may echo a ``document`` on each ranked result even when
        ``return_documents`` is false.  Neither value is part of GaitLogic's
        contract: candidates are local, only their positions and scores are
        trusted, and Provider text must never enter a retrieval response.

        This is a boundary reduction, not a permissive parser.  Required local
        fields remain subject to the strict Pydantic schema below.
        """

        if not isinstance(payload, dict):
            return {"results": payload}
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            return {"results": raw_results}
        return {
            "results": [
                (
                    {
                        "index": item.get("index"),
                        "relevance_score": item.get("relevance_score"),
                    }
                    if isinstance(item, dict)
                    else item
                )
                for item in raw_results
            ]
        }

    def rerank(self, *, query: str, candidates: list[RerankCandidate], top_n: int) -> list[RerankResult]:
        if not candidates or top_n < 1 or top_n > len(candidates):
            raise KnowledgeRerankerError("Reranker candidate request is invalid.")
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": [item.text for item in candidates],
            "instruction": RERANK_INSTRUCTION,
            "top_n": top_n,
            "return_documents": False,
        }
        headers = {"Authorization": f"Bearer {self.settings.knowledge_reranker_effective_api_key}", "Content-Type": "application/json"}
        policy = self._policy()
        response: Any | None = None
        for attempt in range(policy.max_attempts):
            try:
                response = self.client.post(f"{self.base_url}/rerank", headers=headers, json=payload)
            except Exception as exc:
                failure = classify_provider_exception(exc)
                if policy.can_retry(attempt=attempt, failure=failure):
                    self._discard_client(); policy.wait(attempt=attempt, sleeper=self._sleeper); continue
                self._fail(attempt=attempt, policy=policy, category=failure.category, message="Reranker provider is unavailable.", cause=exc)
            status = int(response.status_code)
            if 200 <= status < 300:
                break
            failure = classify_provider_exception(_StatusFailure(status))
            if policy.can_retry(attempt=attempt, failure=failure):
                policy.wait(attempt=attempt, sleeper=self._sleeper); continue
            self._fail(attempt=attempt, policy=policy, category=failure.category, message="Reranker provider rejected the request.")
        try:
            parsed = _Response.model_validate(
                self._response_for_validation(response.json())
            )
            output = self._validate_results(parsed, candidate_count=len(candidates), top_n=top_n)
        except KnowledgeRerankerError:
            raise
        except (ValidationError, ValueError, TypeError) as exc:
            self._fail(attempt=attempt, policy=policy, category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR, message="Reranker provider returned an invalid response.", cause=exc)
        self.last_reliability = ProviderCallReliability(attempt + 1, policy.max_attempts, None, attempt > 0, "SUCCEEDED")
        return output

    def close(self) -> None:
        self._discard_client()
