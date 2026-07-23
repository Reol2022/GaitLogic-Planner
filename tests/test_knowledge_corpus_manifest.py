from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
from server.knowledge_retrieval.errors import KnowledgeBuildError
from server.knowledge_retrieval.manifest import build_manifest, write_manifest_atomic
from server.knowledge_retrieval.validator import KnowledgeCorpusValidator
from server.knowledge_retrieval.errors import KnowledgeValidationError
from tests.knowledge_corpus_helpers import (
    document_metadata,
    write_corpus,
)


def _service(repository: Path, root_name: str = "knowledge") -> KnowledgeCorpusService:
    return KnowledgeCorpusService(
        Path(root_name),
        repository_root=repository,
        output_path=Path(root_name) / "manifests/corpus-v1.json",
    )


def test_root_hash_ignores_generation_time(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    service = _service(tmp_path)
    documents, sources, chunks = service._current_corpus()
    first = build_manifest(
        documents,
        sources,
        chunks,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = build_manifest(
        documents,
        sources,
        chunks,
        generated_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
    assert first.generated_at != second.generated_at
    assert first.root_hash == second.root_hash
    assert root.exists()


def test_build_dry_run_and_repeated_build_are_deterministic(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    service = _service(tmp_path)
    dry_run = service.build(dry_run=True)
    assert dry_run.dry_run is True
    assert not (tmp_path / "knowledge/manifests/corpus-v1.json").exists()
    written = service.build()
    repeated = service.build()
    assert written.written is True
    assert repeated.unchanged is True
    assert repeated.manifest.root_hash == written.manifest.root_hash
    assert [item.chunk_id for item in repeated.manifest.chunks] == [
        item.chunk_id for item in written.manifest.chunks
    ]


def test_changed_manifest_requires_force(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    service = _service(tmp_path)
    original = service.build()
    write_corpus(
        tmp_path,
        metadata=document_metadata(title="更新后的虚构标题"),
    )
    with pytest.raises(KnowledgeBuildError, match="use --force"):
        service.build()
    replaced = service.build(force=True)
    assert replaced.written is True
    assert replaced.manifest.root_hash != original.manifest.root_hash
    assert root.exists()


def test_validate_rejects_stale_manifest(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    service = _service(tmp_path)
    service.build()
    write_corpus(
        tmp_path,
        metadata=document_metadata(title="语料变化后的标题"),
    )
    with pytest.raises(KnowledgeValidationError, match="manifest is stale"):
        service.validate()


def test_manifest_rejects_tampered_chunk_content(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    manifest = _service(tmp_path).validate()
    tampered_chunk = manifest.chunks[0].model_copy(
        update={"content": f"{manifest.chunks[0].content}\n篡改内容"}
    )
    tampered = manifest.model_copy(
        update={"chunks": [tampered_chunk, *manifest.chunks[1:]]}
    )
    with pytest.raises(KnowledgeValidationError, match="content hash"):
        KnowledgeCorpusValidator().validate_manifest(tampered)


def test_status_filters_and_include_options(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    draft = root / "documents/draft.md"
    draft.write_text(
        (root / "documents/document.md")
        .read_text(encoding="utf-8")
        .replace("test-training-document", "draft-training-document")
        .replace("status: ACTIVE", "status: DRAFT"),
        encoding="utf-8",
    )
    deprecated = root / "documents/deprecated.md"
    deprecated.write_text(
        (root / "documents/document.md")
        .read_text(encoding="utf-8")
        .replace("test-training-document", "deprecated-training-document")
        .replace("status: ACTIVE", "status: DEPRECATED"),
        encoding="utf-8",
    )
    service = _service(tmp_path)
    assert len(service.list_documents()) == 1
    assert len(service.list_documents(include_draft=True)) == 2
    assert len(
        service.list_documents(include_draft=True, include_deprecated=True)
    ) == 3


def test_manifest_atomic_failure_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_corpus(tmp_path)
    manifest = _service(tmp_path).validate()
    output = tmp_path / "knowledge/manifests/corpus-v1.json"

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(
        "server.knowledge_retrieval.manifest.os.replace",
        fail_replace,
    )
    with pytest.raises(KnowledgeBuildError, match="atomically"):
        write_manifest_atomic(output, manifest)
    assert not output.exists()
    assert not list(output.parent.glob(".*.tmp"))


def test_document_and_chunk_inspection_contains_no_absolute_path(tmp_path: Path) -> None:
    write_corpus(tmp_path)
    service = _service(tmp_path)
    document = service.inspect_document("test-training-document")
    chunk = service.inspect_chunk(document["chunk_ids"][0])
    assert document["relative_path"] == "documents/document.md"
    assert chunk.metadata.document_path == "documents/document.md"
    assert str(tmp_path) not in str(document)
    assert str(tmp_path) not in chunk.model_dump_json()
