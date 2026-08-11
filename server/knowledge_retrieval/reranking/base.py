"""Strict, transport-neutral contracts for externally supplied rerank scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from server.provider_reliability import ProviderCallReliability


@dataclass(frozen=True)
class RerankCandidate:
    """A locally-owned candidate. Only ``text`` crosses the reranker boundary."""

    chunk_id: str
    text: str


@dataclass(frozen=True)
class RerankResult:
    """Validated index-only response from a reranking Provider."""

    index: int
    relevance_score: float


class Reranker(Protocol):
    provider_kind: str
    model_family: str
    instruction_version: str
    last_reliability: ProviderCallReliability

    def rerank(
        self, *, query: str, candidates: list[RerankCandidate], top_n: int
    ) -> list[RerankResult]: ...
