from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from server.knowledge_retrieval.errors import KnowledgeLoadError, KnowledgePathError
from server.knowledge_retrieval.loader import (
    MAX_KNOWLEDGE_FILE_BYTES,
    KnowledgeCorpusLoader,
)
from server.knowledge_retrieval.paths import CorpusPaths, safe_output_path
from server.knowledge_retrieval.schemas import KnowledgeDocumentMetadata
from tests.knowledge_corpus_helpers import (
    SECTIONS,
    document_metadata,
    source_record,
    write_corpus,
)


def loader_for(repository: Path, root: Path) -> KnowledgeCorpusLoader:
    return KnowledgeCorpusLoader(
        CorpusPaths.create(root, repository_root=repository)
    )


def test_loads_valid_front_matter_and_source(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    documents, sources = loader_for(tmp_path, root).load()
    assert documents[0].metadata.document_id == "test-training-document"
    assert documents[0].relative_path == "documents/document.md"
    assert len(documents[0].file_sha256) == 64
    assert sources[0].relative_path == "sources/sources.yaml"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category", "INVALID"),
        ("source_type", "INVALID"),
        ("evidence_level", "INVALID"),
        ("status", "INVALID"),
        ("knowledge_version", "version-one"),
        ("reviewed_at", "23/07/2026"),
    ],
)
def test_rejects_invalid_controlled_metadata(
    tmp_path: Path, field: str, value: str
) -> None:
    root = write_corpus(
        tmp_path,
        metadata=document_metadata(**{field: value}),
    )
    with pytest.raises(KnowledgeLoadError):
        loader_for(tmp_path, root).load()


def test_schema_rejects_unknown_front_matter_field() -> None:
    with pytest.raises(ValidationError):
        KnowledgeDocumentMetadata.model_validate(
            document_metadata(unexpected="value")
        )


def test_rejects_missing_front_matter(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    (root / "documents/document.md").write_text(SECTIONS, encoding="utf-8")
    with pytest.raises(KnowledgeLoadError, match="missing YAML Front Matter"):
        loader_for(tmp_path, root).load()


def test_rejects_missing_evidence_section(tmp_path: Path) -> None:
    root = write_corpus(
        tmp_path,
        metadata=document_metadata(
            source_id="daniels-running-formula-3rd-edition-cn-summary",
            source_type="BOOK_SUMMARY",
        ),
        sources=[
            source_record(
                source_id="daniels-running-formula-3rd-edition-cn-summary",
                source_type="BOOK_SUMMARY",
                license_status="SUMMARY_ONLY",
                usage_policy="SELF_WRITTEN_SUMMARY",
            )
        ],
        body=SECTIONS.replace("## Evidence", "## 来源"),
    )
    with pytest.raises(KnowledgeLoadError, match="missing required section: Evidence"):
        loader_for(tmp_path, root).load()


def test_accepts_semantic_sections_without_a_fixed_template(tmp_path: Path) -> None:
    body = """## 训练问题

这是一段可独立检索的训练知识。

## Evidence

- Source: 虚构测试来源。
"""
    root = write_corpus(
        tmp_path,
        metadata=document_metadata(
            source_id="daniels-running-formula-3rd-edition-cn-summary",
            source_type="BOOK_SUMMARY",
        ),
        sources=[
            source_record(
                source_id="daniels-running-formula-3rd-edition-cn-summary",
                source_type="BOOK_SUMMARY",
                license_status="SUMMARY_ONLY",
                usage_policy="SELF_WRITTEN_SUMMARY",
            )
        ],
        body=body,
    )
    documents, _ = loader_for(tmp_path, root).load()
    assert documents[0].metadata.document_id == "test-training-document"


def test_rejects_missing_source_and_source_type_mismatch(tmp_path: Path) -> None:
    missing_root = write_corpus(
        tmp_path / "missing",
        metadata=document_metadata(source_id="not-registered"),
    )
    with pytest.raises(KnowledgeLoadError, match="source_id does not exist"):
        loader_for(tmp_path / "missing", missing_root).load()

    mismatch_root = write_corpus(
        tmp_path / "mismatch",
        metadata=document_metadata(source_type="BOOK_SUMMARY"),
    )
    with pytest.raises(KnowledgeLoadError, match="source_type does not match"):
        loader_for(tmp_path / "mismatch", mismatch_root).load()


def test_rejects_duplicate_document_and_source_ids(tmp_path: Path) -> None:
    source_root = write_corpus(
        tmp_path / "source",
        sources=[source_record(), source_record()],
    )
    with pytest.raises(KnowledgeLoadError, match="Duplicate source_id"):
        loader_for(tmp_path / "source", source_root).load()

    document_root = write_corpus(tmp_path / "document")
    original = document_root / "documents/document.md"
    (document_root / "documents/copy.md").write_bytes(original.read_bytes())
    with pytest.raises(KnowledgeLoadError, match="Duplicate document_id"):
        loader_for(tmp_path / "document", document_root).load()


def test_ignores_hidden_and_temporary_files(tmp_path: Path) -> None:
    root = write_corpus(tmp_path)
    (root / "documents/.hidden.md").write_text("invalid", encoding="utf-8")
    (root / "documents/document.md.tmp").write_text("invalid", encoding="utf-8")
    documents, _ = loader_for(tmp_path, root).load()
    assert len(documents) == 1


def test_rejects_oversized_and_non_utf8_files(tmp_path: Path) -> None:
    oversized = write_corpus(tmp_path / "large")
    (oversized / "documents/document.md").write_bytes(
        b"x" * (MAX_KNOWLEDGE_FILE_BYTES + 1)
    )
    with pytest.raises(KnowledgeLoadError, match="file exceeds"):
        loader_for(tmp_path / "large", oversized).load()

    invalid = write_corpus(tmp_path / "encoding")
    (invalid / "documents/document.md").write_bytes(b"\xff\xfe")
    with pytest.raises(KnowledgeLoadError, match="must be UTF-8"):
        loader_for(tmp_path / "encoding", invalid).load()


def test_supports_chinese_and_space_paths(tmp_path: Path) -> None:
    repository = tmp_path / "中文 项目"
    root = write_corpus(repository, root_name="训练 知识")
    documents, _ = loader_for(repository, root).load()
    assert documents[0].metadata.title == "虚构训练知识"


def test_rejects_absolute_and_traversing_output_paths(tmp_path: Path) -> None:
    with pytest.raises(KnowledgePathError):
        safe_output_path(tmp_path / "manifest.json", tmp_path)
    with pytest.raises(KnowledgePathError):
        safe_output_path(Path("../manifest.json"), tmp_path)


def test_symlink_outside_root_is_rejected(tmp_path: Path) -> None:
    root = write_corpus(tmp_path / "repo")
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = root / "documents/escape.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")
    with pytest.raises(KnowledgeLoadError, match="Symlink escapes"):
        loader_for(tmp_path / "repo", root).load()


def test_rejects_script_and_remote_include(tmp_path: Path) -> None:
    script_root = write_corpus(
        tmp_path / "script",
        body=f"{SECTIONS}\n<script>alert(1)</script>",
    )
    with pytest.raises(KnowledgeLoadError, match="HTML script"):
        loader_for(tmp_path / "script", script_root).load()
    include_root = write_corpus(
        tmp_path / "include",
        body=f'{SECTIONS}\n!INCLUDE "https://example.invalid/private.md"',
    )
    with pytest.raises(KnowledgeLoadError, match="remote includes"):
        loader_for(tmp_path / "include", include_root).load()


def test_validator_rejects_user_identity_and_machine_paths(tmp_path: Path) -> None:
    from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
    from server.knowledge_retrieval.errors import KnowledgeValidationError

    identity_root = write_corpus(
        tmp_path / "identity",
        body=SECTIONS.replace(
            "适用于虚构测试场景。",
            "适用于虚构测试场景，联系 runner@example.com。",
        ),
    )
    identity_service = KnowledgeCorpusService(
        identity_root,
        repository_root=tmp_path / "identity",
        output_path=Path("knowledge/manifests/corpus-v1.json"),
    )
    with pytest.raises(KnowledgeValidationError, match="user identity"):
        identity_service.validate()

    path_root = write_corpus(
        tmp_path / "path",
        body=SECTIONS.replace(
            "适用于虚构测试场景。",
            r"材料来自 C:\private\training.txt。",
        ),
    )
    path_service = KnowledgeCorpusService(
        path_root,
        repository_root=tmp_path / "path",
        output_path=Path("knowledge/manifests/corpus-v1.json"),
    )
    with pytest.raises(KnowledgeValidationError, match="absolute machine path"):
        path_service.validate()
