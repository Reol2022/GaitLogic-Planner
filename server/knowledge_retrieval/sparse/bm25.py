"""Offline, deterministic BM25 for the versioned mixed-language corpus.

The analyzer deliberately does not use English stemming or an English
stop-word list: those defaults would silently change Chinese and mixed Chinese
and English retrieval.  CJK text is represented by stable unigrams and
adjacent bigrams; ASCII technical terms, abbreviations, and numeric units stay
intact after Unicode NFKC normalisation and lowercase conversion.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
import unicodedata


ANALYZER_VERSION = "gaitlogic-mixed-bm25-1"
BM25_K1 = 1.2
BM25_B = 0.75
_ASCII_TERM = re.compile(r"[a-z0-9]+(?:[._/+\-][a-z0-9]+)*", re.IGNORECASE)
_CJK_BLOCK = re.compile(r"[\u3400-\u9fff]+")


@dataclass(frozen=True)
class Bm25Document:
    chunk_id: str
    document_id: str
    content_sha256: str
    category: str
    tags: tuple[str, ...]
    language: str
    term_frequencies: dict[str, int]
    document_length: int


class BM25Analyzer:
    """A documented, dependency-free analyzer for public knowledge chunks."""

    version = ANALYZER_VERSION

    @staticmethod
    def tokenize(text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text).lower()
        tokens = _ASCII_TERM.findall(normalized)
        for block in _CJK_BLOCK.findall(normalized):
            tokens.extend(block)
            tokens.extend(block[index : index + 2] for index in range(len(block) - 1))
        return tokens


class BM25Index:
    """Read-only lexical scorer.  Tie-breaking is always by chunk ID."""

    def __init__(
        self,
        documents: list[Bm25Document],
        *,
        k1: float = BM25_K1,
        b: float = BM25_B,
    ) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 configuration is invalid.")
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self.document_frequency: Counter[str] = Counter()
        for document in self.documents:
            self.document_frequency.update(document.term_frequencies)
        self.average_length = (
            sum(document.document_length for document in self.documents) / len(self.documents)
            if self.documents
            else 0.0
        )

    @property
    def config(self) -> dict[str, object]:
        return {
            "strategy": "bm25_v1",
            "analyzer_version": ANALYZER_VERSION,
            "k1": self.k1,
            "b": self.b,
        }

    @staticmethod
    def _matches(document: Bm25Document, *, categories: set[str], tags: set[str], language: str | None) -> bool:
        if categories and document.category not in categories:
            return False
        if tags and not tags.issubset(set(document.tags)):
            return False
        return language is None or document.language == language

    def search(
        self,
        query: str,
        *,
        top_k: int,
        categories: set[str] | None = None,
        tags: set[str] | None = None,
        language: str | None = None,
    ) -> list[tuple[Bm25Document, float]]:
        query_terms = Counter(BM25Analyzer.tokenize(query))
        if not query_terms or not self.documents:
            return []
        total_documents = len(self.documents)
        candidates: list[tuple[Bm25Document, float]] = []
        for document in self.documents:
            if not self._matches(
                document,
                categories=categories or set(),
                tags=tags or set(),
                language=language,
            ):
                continue
            score = 0.0
            length_ratio = document.document_length / max(self.average_length, 1.0)
            for term, query_frequency in query_terms.items():
                frequency = document.term_frequencies.get(term, 0)
                if not frequency:
                    continue
                frequency_in_corpus = self.document_frequency[term]
                inverse_document_frequency = math.log(
                    1.0 + (total_documents - frequency_in_corpus + 0.5) / (frequency_in_corpus + 0.5)
                )
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * length_ratio)
                score += (
                    inverse_document_frequency
                    * (frequency * (self.k1 + 1.0) / denominator)
                    * query_frequency
                )
            if score > 0:
                candidates.append((document, score))
        candidates.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return candidates[:top_k]
