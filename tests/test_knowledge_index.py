from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.errors import KnowledgeIndexError
from server.knowledge_retrieval.index_manifest import (
    build_index_manifest,
    calculate_index_root_hash,
    validate_index_manifest,
    vector_sha256,
)
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from tests.knowledge_index_helpers import (
    build_test_index,
    prepare_repository,
    vector_record,
)


class AlternateDeterministicProvider(DeterministicEmbeddingProvider):
    def _embed(self, text: str, *, limit: int) -> list[float]:
        vector = super()._embed(text, limit=limit)
        return [-value for value in vector]


def test_index_build_plan_does_not_write(tmp_path: Path) -> None:
    service = prepare_repository(tmp_path)
    plan = service.build(
        DeterministicEmbeddingProvider(dimensions=32),
        dry_run=True,
    )
    assert plan.chunk_count == 60
    assert plan.estimated_batches == 1
    assert not (tmp_path / "var/knowledge_indexes").exists()


def test_index_build_validate_list_and_inspect(tmp_path: Path) -> None:
    service, index_id = build_test_index(tmp_path)
    manifest = service.validate(index_id)
    assert manifest.chunk_count == 60
    assert manifest.embedding_dimensions == 32
    assert service.list_indexes()[0].index_id == index_id
    inspected = service.inspect(index_id)
    assert inspected["relative_path"].startswith("var/knowledge_indexes/")
    assert str(tmp_path) not in str(inspected)


def test_repeated_deterministic_build_is_unchanged(tmp_path: Path) -> None:
    service = prepare_repository(tmp_path)
    first = service.build(DeterministicEmbeddingProvider(dimensions=32))
    second = service.build(DeterministicEmbeddingProvider(dimensions=32))
    assert second.unchanged is True
    assert first.manifest.root_hash == second.manifest.root_hash
    assert first.manifest.vector_hashes == second.manifest.vector_hashes


def test_different_vectors_require_force(tmp_path: Path) -> None:
    service = prepare_repository(tmp_path)
    original = service.build(DeterministicEmbeddingProvider(dimensions=32))
    with pytest.raises(KnowledgeIndexError, match="--force"):
        service.build(AlternateDeterministicProvider(dimensions=32))
    replaced = service.build(
        AlternateDeterministicProvider(dimensions=32),
        force=True,
    )
    assert replaced.manifest.index_id == original.manifest.index_id
    assert replaced.manifest.root_hash != original.manifest.root_hash


def test_corrupt_vector_store_and_stale_corpus_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, index_id = build_test_index(tmp_path)
    store = (
        tmp_path
        / "var/knowledge_indexes"
        / index_id
        / "store/records.json"
    )
    original = store.read_bytes()
    store.write_text("[]", encoding="utf-8")
    with pytest.raises(KnowledgeIndexError, match="record count"):
        service.validate(index_id)
    store.write_bytes(original)

    corpus = service._corpus()
    monkeypatch.setattr(
        service,
        "_corpus",
        lambda: corpus.model_copy(update={"root_hash": "f" * 64}),
    )
    with pytest.raises(KnowledgeIndexError, match="stale"):
        service.validate(index_id)


def test_index_atomic_failure_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = prepare_repository(tmp_path)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(
        "server.knowledge_retrieval.index_service.os.replace",
        fail_replace,
    )
    with pytest.raises(OSError):
        service.build(DeterministicEmbeddingProvider(dimensions=32))
    index_root = tmp_path / "var/knowledge_indexes"
    assert not list(index_root.glob(".*.tmp"))
    assert not list(index_root.glob(".*.bak"))


def test_index_manifest_root_ignores_created_at_and_binds_configuration() -> None:
    record = vector_record()
    first = build_index_manifest(
        corpus_root_hash="b" * 64,
        corpus_manifest_sha256="c" * 64,
        embedding_provider="deterministic_test",
        embedding_model="model-a",
        embedding_dimensions=2,
        embedding_normalized=True,
        records=[record],
        warnings=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = build_index_manifest(
        corpus_root_hash="b" * 64,
        corpus_manifest_sha256="c" * 64,
        embedding_provider="deterministic_test",
        embedding_model="model-a",
        embedding_dimensions=2,
        embedding_normalized=True,
        records=[record],
        warnings=[],
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
    assert first.root_hash == second.root_hash
    assert first.index_id == second.index_id

    changed = first.model_copy(update={"embedding_model": "model-b"})
    assert calculate_index_root_hash(changed) != first.root_hash
    assert vector_sha256([1.0, 0.0]) != vector_sha256([0.0, 1.0])


def test_index_manifest_rejects_tamper_absolute_path_and_secret() -> None:
    record = vector_record()
    manifest = build_index_manifest(
        corpus_root_hash="b" * 64,
        corpus_manifest_sha256="c" * 64,
        embedding_provider="deterministic_test",
        embedding_model="model",
        embedding_dimensions=2,
        embedding_normalized=True,
        records=[record],
        warnings=[],
    )
    with pytest.raises(KnowledgeIndexError, match="root hash"):
        validate_index_manifest(
            manifest.model_copy(update={"root_hash": "d" * 64})
        )
    with pytest.raises(KnowledgeIndexError, match="absolute path"):
        validate_index_manifest(
            manifest.model_copy(update={"warnings": [r"C:\private\index"]})
        )
    with pytest.raises(KnowledgeIndexError, match="secret field"):
        validate_index_manifest(
            manifest.model_copy(update={"warnings": ["api_key is forbidden"]})
        )


def test_remote_provider_reproducibility_limitation_is_recorded(
    tmp_path: Path,
) -> None:
    class RemoteLike(DeterministicEmbeddingProvider):
        provider_name = "openai_compatible"
        model_name = "fictional-remote-model"

    service = prepare_repository(tmp_path)
    result = service.build(RemoteLike(dimensions=32))
    assert any("may change over time" in item for item in result.manifest.warnings)


def test_index_directory_is_git_ignored() -> None:
    repository = Path(__file__).resolve().parents[1]
    ignore = (repository / ".gitignore").read_text(encoding="utf-8")
    assert "var/knowledge_indexes/" in ignore
