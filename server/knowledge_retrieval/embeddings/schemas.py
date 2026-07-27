from __future__ import annotations

import math

from pydantic import Field, field_validator, model_validator

from server.knowledge_retrieval.schemas import StrictModel


MAX_EMBEDDING_DIMENSIONS = 65536


def validate_vector(value: list[float]) -> list[float]:
    if not value:
        raise ValueError("Embedding vector cannot be empty.")
    if len(value) > MAX_EMBEDDING_DIMENSIONS:
        raise ValueError("Embedding vector exceeds the dimensions limit.")
    normalized = [float(item) for item in value]
    if not all(math.isfinite(item) for item in normalized):
        raise ValueError("Embedding vector must contain only finite values.")
    return normalized


class EmbeddingUsage(StrictModel):
    input_count: int = Field(default=0, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class EmbeddingVector(StrictModel):
    vector: list[float]
    dimensions: int = Field(ge=1, le=MAX_EMBEDDING_DIMENSIONS)
    provider: str
    model: str
    normalized: bool
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("vector")
    @classmethod
    def vector_is_valid(cls, value: list[float]) -> list[float]:
        return validate_vector(value)

    @model_validator(mode="after")
    def dimensions_match(self) -> EmbeddingVector:
        if len(self.vector) != self.dimensions:
            raise ValueError("Embedding dimensions do not match vector length.")
        return self


class EmbeddingBatch(StrictModel):
    vectors: list[list[float]]
    dimensions: int = Field(ge=1, le=MAX_EMBEDDING_DIMENSIONS)
    provider: str
    model: str
    normalized: bool
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("vectors")
    @classmethod
    def vectors_are_valid(cls, values: list[list[float]]) -> list[list[float]]:
        if not values:
            raise ValueError("Embedding batch cannot be empty.")
        return [validate_vector(value) for value in values]

    @model_validator(mode="after")
    def dimensions_match(self) -> EmbeddingBatch:
        if any(len(vector) != self.dimensions for vector in self.vectors):
            raise ValueError("Embedding batch contains inconsistent dimensions.")
        return self
