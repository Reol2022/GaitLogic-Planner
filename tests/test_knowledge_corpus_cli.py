from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import knowledge_corpus
from tests.knowledge_corpus_helpers import write_corpus


def _configure_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(knowledge_corpus, "REPOSITORY_ROOT", tmp_path)


def test_cli_validate_list_and_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_corpus(tmp_path)
    _configure_repository(monkeypatch, tmp_path)
    assert knowledge_corpus.main(["validate"]) == 0
    assert "Corpus valid" in capsys.readouterr().out
    assert knowledge_corpus.main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["document_id"] == "test-training-document"
    assert str(tmp_path) not in json.dumps(payload)


def test_cli_build_and_inspect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_corpus(tmp_path)
    _configure_repository(monkeypatch, tmp_path)
    assert knowledge_corpus.main(["build", "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out
    assert knowledge_corpus.main(["build"]) == 0
    capsys.readouterr()
    assert (
        knowledge_corpus.main(
            ["inspect", "--document-id", "test-training-document"]
        )
        == 0
    )
    document = json.loads(capsys.readouterr().out)
    assert document["relative_path"] == "documents/document.md"
    chunk_id = document["chunk_ids"][0]
    assert knowledge_corpus.main(["inspect", "--chunk-id", chunk_id]) == 0
    chunk = json.loads(capsys.readouterr().out)
    assert chunk["chunk_id"] == chunk_id


def test_cli_rejects_absolute_and_traversing_paths() -> None:
    with pytest.raises(SystemExit):
        knowledge_corpus.main(["validate", "--root", "C:\\private\\knowledge"])
    with pytest.raises(SystemExit):
        knowledge_corpus.main(["build", "--output", "../manifest.json"])


def test_cli_returns_safe_error_for_unknown_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_corpus(tmp_path)
    _configure_repository(monkeypatch, tmp_path)
    assert (
        knowledge_corpus.main(["inspect", "--document-id", "not-found"]) == 2
    )
    error = capsys.readouterr().err
    assert "Document not found" in error
    assert str(tmp_path) not in error
