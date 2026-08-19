"""Provider-neutral reliability policy with safe, stable failure categories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import sleep
from typing import Callable

import httpx


class ProviderFailureCategory(str, Enum):
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_CONNECTION_ERROR = "PROVIDER_CONNECTION_ERROR"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_AUTH_ERROR = "PROVIDER_AUTH_ERROR"
    PROVIDER_BAD_REQUEST = "PROVIDER_BAD_REQUEST"
    PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
    PROVIDER_INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
    PROVIDER_OUTPUT_TRUNCATED = "PROVIDER_OUTPUT_TRUNCATED"
    PROVIDER_EMPTY_CONTENT = "PROVIDER_EMPTY_CONTENT"
    PROVIDER_INVALID_JSON = "PROVIDER_INVALID_JSON"
    PROVIDER_SCHEMA_ERROR = "PROVIDER_SCHEMA_ERROR"
    PROVIDER_TOOL_PROTOCOL_ERROR = "PROVIDER_TOOL_PROTOCOL_ERROR"
    PROVIDER_EMBEDDING_DIMENSION_ERROR = "PROVIDER_EMBEDDING_DIMENSION_ERROR"
    PROVIDER_UNKNOWN_ERROR = "PROVIDER_UNKNOWN_ERROR"


RETRYABLE_PROVIDER_FAILURES = frozenset(
    {
        ProviderFailureCategory.PROVIDER_TIMEOUT,
        ProviderFailureCategory.PROVIDER_CONNECTION_ERROR,
        ProviderFailureCategory.PROVIDER_RATE_LIMIT,
        ProviderFailureCategory.PROVIDER_SERVER_ERROR,
        ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED,
    }
)


@dataclass(frozen=True)
class ProviderFailure:
    """Safe classification; it deliberately carries no raw Provider details."""

    category: ProviderFailureCategory
    retryable: bool


@dataclass(frozen=True)
class ProviderCallReliability:
    """Safe summary of the latest call, suitable for Trace and Evaluation."""

    attempts: int
    max_attempts: int
    failure_category: ProviderFailureCategory | None
    retried: bool
    final_status: str


@dataclass(frozen=True)
class RetryPolicy:
    """Small bounded exponential backoff policy for a single Provider call."""

    max_retries: int
    initial_backoff_seconds: float
    max_backoff_seconds: float

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.initial_backoff_seconds < 0 or self.max_backoff_seconds < 0:
            raise ValueError("backoff cannot be negative")
        if self.initial_backoff_seconds > self.max_backoff_seconds:
            raise ValueError("initial backoff cannot exceed max backoff")

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    def can_retry(self, *, attempt: int, failure: ProviderFailure) -> bool:
        return failure.retryable and attempt + 1 < self.max_attempts

    def delay_for_retry(self, *, attempt: int) -> float:
        return min(
            self.initial_backoff_seconds * (2**attempt),
            self.max_backoff_seconds,
        )

    def wait(self, *, attempt: int, sleeper: Callable[[float], None] = sleep) -> float:
        delay = self.delay_for_retry(attempt=attempt)
        if delay > 0:
            sleeper(delay)
        return delay


def provider_failure(category: ProviderFailureCategory) -> ProviderFailure:
    return ProviderFailure(
        category=category,
        retryable=category in RETRYABLE_PROVIDER_FAILURES,
    )


def classify_provider_exception(exc: Exception) -> ProviderFailure:
    """Classify transport exceptions and HTTP-style SDK exceptions safely."""

    status = getattr(exc, "status_code", None)
    if status == 429:
        return provider_failure(ProviderFailureCategory.PROVIDER_RATE_LIMIT)
    if status in {401, 403}:
        return provider_failure(ProviderFailureCategory.PROVIDER_AUTH_ERROR)
    if status == 400:
        return provider_failure(ProviderFailureCategory.PROVIDER_BAD_REQUEST)
    if isinstance(status, int) and 500 <= status <= 599:
        return provider_failure(ProviderFailureCategory.PROVIDER_SERVER_ERROR)
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    if isinstance(exc, (httpx.TransportError, ConnectionError, OSError)):
        return provider_failure(ProviderFailureCategory.PROVIDER_CONNECTION_ERROR)
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    if "connection" in name or "connect" in name:
        return provider_failure(ProviderFailureCategory.PROVIDER_CONNECTION_ERROR)
    return provider_failure(ProviderFailureCategory.PROVIDER_UNKNOWN_ERROR)
