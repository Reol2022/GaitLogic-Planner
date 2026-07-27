from __future__ import annotations

import hashlib
import math
import re
import unicodedata

from server.knowledge_retrieval.embeddings.schemas import (
    EmbeddingBatch,
    EmbeddingUsage,
    EmbeddingVector,
)
from server.knowledge_retrieval.errors import (
    KnowledgeEmbeddingConfigurationError,
    KnowledgeEmbeddingError,
)


TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+|[\u3400-\u4dbf\u4e00-\u9fff]")
MAX_TEXT_CHARS = 20000
MAX_QUERY_CHARS = 4000


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise KnowledgeEmbeddingError("Embedding vector norm must be positive.")
    return [value / norm for value in vector]


class DeterministicEmbeddingProvider:
    """Stable lexical hashing for tests and offline plumbing, not semantic search."""

    provider_name = "deterministic_test"
    model_name = "sha256-lexical-v1"
    normalized = True

    def __init__(
        self,
        *,
        dimensions: int = 64,
        max_batch_size: int = 64,
        environment: str = "development",
    ) -> None:
        if environment.lower() == "production":
            raise KnowledgeEmbeddingConfigurationError(
                "deterministic_test embedding is not allowed in production."
            )
        if dimensions < 8 or dimensions > 4096:
            raise KnowledgeEmbeddingConfigurationError(
                "Deterministic embedding dimensions must be between 8 and 4096."
            )
        if max_batch_size < 1 or max_batch_size > 128:
            raise KnowledgeEmbeddingConfigurationError(
                "Embedding batch size must be between 1 and 128."
            )
        self.dimensions = dimensions
        self.max_batch_size = max_batch_size

    @staticmethod
    def _validate_text(text: str, *, limit: int) -> str:
        value = text.strip()
        if not value:
            raise KnowledgeEmbeddingError("Embedding input cannot be empty.")
        if len(value) > limit:
            raise KnowledgeEmbeddingError("Embedding input exceeds the length limit.")
        return value

    def _embed(self, text: str, *, limit: int) -> list[float]:
        value = unicodedata.normalize(
            "NFKC",
            self._validate_text(text, limit=limit),
        ).lower()
        tokens = TOKEN_RE.findall(value)
        features = tokens + [
            f"{tokens[index]}::{tokens[index + 1]}"
            for index in range(len(tokens) - 1)
        ]
        if not features:
            features = [value]
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            sign = 1.0 if digest[8] & 1 else -1.0
            weight = 1.0 + digest[9] / 2550.0
            vector[index] += sign * weight
        return normalize_vector(vector)

    def embed_documents(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            raise KnowledgeEmbeddingError("Embedding document batch cannot be empty.")
        if len(texts) > self.max_batch_size:
            raise KnowledgeEmbeddingError("Embedding document batch is too large.")
        vectors = [
            self._embed(text, limit=MAX_TEXT_CHARS)
            for text in texts
        ]
        return EmbeddingBatch(
            vectors=vectors,
            dimensions=self.dimensions,
            provider=self.provider_name,
            model=self.model_name,
            normalized=True,
            usage=EmbeddingUsage(input_count=len(texts)),
            warnings=[
                "deterministic_test validates index plumbing only; it has no "
                "production semantic-quality claim."
            ],
        )

    def embed_query(self, text: str) -> EmbeddingVector:
        return EmbeddingVector(
            vector=self._embed(text, limit=MAX_QUERY_CHARS),
            dimensions=self.dimensions,
            provider=self.provider_name,
            model=self.model_name,
            normalized=True,
            usage=EmbeddingUsage(input_count=1),
            warnings=[
                "deterministic_test validates index plumbing only; it has no "
                "production semantic-quality claim."
            ],
        )

    def close(self) -> None:
        return None
