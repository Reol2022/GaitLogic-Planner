from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import knowledge_index
from tests.knowledge_index_helpers import CORPUS_MANIFEST


def _repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "knowledge/manifests"
    target.mkdir(parents=True)
    (target / "corpus-v1.json").write_bytes(CORPUS_MANIFEST.read_bytes())
    monkeypatch.setattr(knowledge_index, "REPOSITORY_ROOT", tmp_path)


def test_cli_dry_run_build_validate_list_inspect_and_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _repository(tmp_path, monkeypatch)
    assert knowledge_index.main(["build", "--dry-run"]) == 0
    assert "dry-run" in capsys.readouterr().out
    assert knowledge_index.main(["build", "--json"]) == 0
    build = json.loads(capsys.readouterr().out)
    index_id = build["manifest"]["index_id"]
    assert knowledge_index.main(["validate", "--index-id", index_id]) == 0
    assert "Index valid" in capsys.readouterr().out
    assert knowledge_index.main(["list", "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing[0]["index_id"] == index_id
    assert knowledge_index.main(["inspect", "--index-id", index_id]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["index_id"] == index_id
    assert str(tmp_path) not in json.dumps(inspected)
    assert (
        knowledge_index.main(
            [
                "query",
                "--text",
                "疲劳恢复",
                "--category",
                "RECOVERY",
                "--top-k",
                "2",
            ]
        )
        == 0
    )
    query = json.loads(capsys.readouterr().out)
    assert len(query["results"]) == 2
    assert all(item["category"] == "RECOVERY" for item in query["results"])


def test_cli_repeated_build_is_unchanged_and_force_is_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _repository(tmp_path, monkeypatch)
    assert knowledge_index.main(["build"]) == 0
    capsys.readouterr()
    assert knowledge_index.main(["build"]) == 0
    assert "unchanged" in capsys.readouterr().out
    assert knowledge_index.main(["build", "--force"]) == 0


def test_cli_rejects_unsafe_paths() -> None:
    with pytest.raises(SystemExit):
        knowledge_index.main(
            ["build", "--index-dir", r"C:\private\index"]
        )
    with pytest.raises(SystemExit):
        knowledge_index.main(
            ["validate", "--corpus-manifest", "../corpus.json"]
        )
