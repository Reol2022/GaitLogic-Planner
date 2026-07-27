from __future__ import annotations

import math
import re
from collections import Counter

from server.knowledge_retrieval.evaluation.schemas import RankedItem, RetrievalEvaluationCase
from server.knowledge_retrieval.schemas import CorpusManifest

ASCII_TOKEN = re.compile(r"[a-z0-9]+")
CJK_BLOCK = re.compile(r"[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = ASCII_TOKEN.findall(lowered)
    for block in CJK_BLOCK.findall(lowered):
        tokens.extend(block[index : index + 2] for index in range(max(1, len(block) - 1)))
    return tokens


class LexicalBm25Baseline:
    """Small deterministic BM25 baseline used only by evaluation."""

    def __init__(self, corpus: CorpusManifest) -> None:
        self.chunks = list(corpus.chunks)
        self.tokens = {item.chunk_id: tokenize(item.content) for item in self.chunks}
        self.document_frequency: Counter[str] = Counter()
        for values in self.tokens.values():
            self.document_frequency.update(set(values))
        self.average_length = (
            sum(len(values) for values in self.tokens.values()) / len(self.tokens)
            if self.tokens
            else 0.0
        )

    def _matches_filters(self, chunk, case: RetrievalEvaluationCase) -> bool:
        if case.filters.categories and chunk.category not in case.filters.categories:
            return False
        if case.filters.tags and not set(case.filters.tags).issubset(set(chunk.tags)):
            return False
        return chunk.metadata.language == case.language

    def search(self, case: RetrievalEvaluationCase, *, top_k: int = 4) -> list[RankedItem]:
        query = Counter(tokenize(case.query))
        if not query:
            return []
        total = max(len(self.chunks), 1)
        scored: list[tuple[float, object]] = []
        for chunk in self.chunks:
            if not self._matches_filters(chunk, case):
                continue
            terms = Counter(self.tokens[chunk.chunk_id])
            score = 0.0
            length = max(len(self.tokens[chunk.chunk_id]), 1)
            for term, query_frequency in query.items():
                frequency = terms[term]
                if not frequency:
                    continue
                df = self.document_frequency[term]
                inverse = math.log(1 + (total - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.5 * (
                    1 - 0.75 + 0.75 * length / max(self.average_length, 1.0)
                )
                score += inverse * frequency * 2.5 / denominator * query_frequency
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        return [
            RankedItem(
                rank=rank,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                score=round(score, 8),
            )
            for rank, (score, chunk) in enumerate(scored[:top_k], start=1)
        ]
