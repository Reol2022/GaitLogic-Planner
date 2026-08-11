"""Deterministic rank-only fusion strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FusionRank:
    chunk_id: str
    dense_rank: int | None
    bm25_rank: int | None
    fusion_score: float


class ReciprocalRankFusion:
    """Equal-weight RRF.  Never mixes incomparable dense and BM25 raw scores."""

    name = "rrf"

    def __init__(self, *, rank_constant: int = 60) -> None:
        if rank_constant < 1:
            raise ValueError("RRF rank_constant must be positive.")
        self.rank_constant = rank_constant

    def fuse(
        self,
        *,
        dense_chunk_ids: Iterable[str],
        bm25_chunk_ids: Iterable[str],
        top_k: int,
    ) -> list[FusionRank]:
        if top_k < 1:
            raise ValueError("Fusion top_k must be positive.")
        positions: dict[str, dict[str, int]] = {}
        for source, values in (("dense", dense_chunk_ids), ("bm25", bm25_chunk_ids)):
            for rank, chunk_id in enumerate(values, start=1):
                # A backend should already deduplicate, but RRF is defensive.
                positions.setdefault(chunk_id, {}).setdefault(source, rank)
        results = [
            FusionRank(
                chunk_id=chunk_id,
                dense_rank=item.get("dense"),
                bm25_rank=item.get("bm25"),
                fusion_score=sum(1.0 / (self.rank_constant + rank) for rank in item.values()),
            )
            for chunk_id, item in positions.items()
        ]
        return sorted(results, key=lambda item: (-item.fusion_score, item.chunk_id))[:top_k]
