from __future__ import annotations

import pytest
from pydantic import ValidationError

from planner_core.config import Settings
from server.knowledge_retrieval.vector_stores.factory import vector_store_name


def test_exact_store_remains_the_default() -> None:
    settings = Settings(_env_file=None)
    assert settings.knowledge_vector_store == "exact"
    assert vector_store_name(settings.knowledge_vector_store) == "exact_cosine_v1"


def test_qdrant_configuration_is_explicit_and_url_has_no_credentials() -> None:
    settings = Settings(
        _env_file=None,
        KNOWLEDGE_VECTOR_STORE="qdrant",
        QDRANT_URL="https://qdrant.example.test:6333",
        QDRANT_COLLECTION_PREFIX="gaitlogic_prod",
    )
    assert settings.knowledge_vector_store == "qdrant"
    assert settings.qdrant_url == "https://qdrant.example.test:6333"
    with pytest.raises(ValidationError, match="Qdrant URL"):
        Settings(_env_file=None, QDRANT_URL="https://token@example.test?secret=x")


def test_unknown_store_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported vector store"):
        vector_store_name("hybrid")
