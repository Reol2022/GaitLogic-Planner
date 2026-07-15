from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrainingKnowledgeItemRead(BaseModel):
    id: int
    code: str
    name: str
    english_name: str | None = None
    category: str
    definition: str
    aliases_json: list[str] = Field(default_factory=list)
    attributes_json: dict[str, Any] = Field(default_factory=dict)
    related_codes_json: list[str] = Field(default_factory=list)
    source_refs_json: list[str] = Field(default_factory=list)
    evidence_level: str
    version: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingKnowledgeItemsResponse(BaseModel):
    items: list[TrainingKnowledgeItemRead]
    total: int
    limit: int
    offset: int


class TrainingKnowledgeCategoriesResponse(BaseModel):
    categories: list[str]

