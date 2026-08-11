from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

import pytest

from planner_core.config import Settings
from scripts.check_coach_rag_readiness import main
from server.knowledge_retrieval.embeddings.deterministic import (
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
from server.knowledge_retrieval.readiness import (
    CoachRagReadinessService,
    ReadinessExitCode,
)


class ConfiguredEmbeddingProvider(DeterministicEmbeddingProvider):
    provider_name = "openai_compatible"
    model_name = "fictional-embedding-model"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "APP_ENV": "production",
        "COACH_AGENT_ENABLED": True,
        "COACH_AGENT_PROVIDER": "openai-compatible",
        "COACH_AGENT_API_KEY": "fictional-chat-secret",
        "COACH_AGENT_BASE_URL": "https://chat.example.test/v1",
        "COACH_AGENT_MODEL": "fictional-chat-model",
        "KNOWLEDGE_EMBEDDING_ENABLED": True,
        "KNOWLEDGE_EMBEDDING_PROVIDER": "openai_compatible",
        "KNOWLEDGE_EMBEDDING_API_KEY": "fictional-embedding-secret",
        "KNOWLEDGE_EMBEDDING_BASE_URL": "https://embedding.example.test/v1",
        "KNOWLEDGE_EMBEDDING_MODEL": "fictional-embedding-model",
        "KNOWLEDGE_EMBEDDING_DIMENSIONS": 32,
        "COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED": True,
        "COACH_AGENT_KNOWLEDGE_INDEX_ID": "",
        "KNOWLEDGE_INDEX_RUNTIME_DIRECTORY": "var/knowledge_indexes",
        "KNOWLEDGE_INDEX_MAX_AGE_DAYS": 30,
    }
    values.update(overrides)
    return Settings(**values)


def _ready_repository(tmp_path: Path) -> tuple[Settings, Path]:
    source_root = Path(__file__).resolve().parents[1]
    shutil.copytree(source_root / "knowledge", tmp_path / "knowledge")
    (tmp_path / ".gitignore").write_text(
        "var/knowledge_indexes/\n",
        encoding="utf-8",
    )
    # Build the derived manifest from the copied fixture. Git may normalize
    # Markdown line endings differently across Windows and Linux checkouts,
    # so copying a manifest generated in another checkout is not a stable
    # representation of this temporary repository.
    KnowledgeCorpusService(repository_root=tmp_path).build(force=True)
    result = KnowledgeIndexService(repository_root=tmp_path).build(
        ConfiguredEmbeddingProvider(dimensions=32)
    )
    settings = _settings(
        COACH_AGENT_KNOWLEDGE_INDEX_ID=result.manifest.index_id
    )
    return settings, tmp_path


def test_disabled_features_are_safe_and_require_enabled_fails(
    tmp_path: Path,
) -> None:
    settings = _settings(
        COACH_AGENT_ENABLED=False,
        COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=False,
    )
    optional = CoachRagReadinessService(
        settings, repository_root=tmp_path
    ).run()
    required = CoachRagReadinessService(
        settings, repository_root=tmp_path
    ).run(require_enabled=True)
    assert optional.ready is True
    assert required.exit_code == ReadinessExitCode.FEATURE_DISABLED


def test_coach_only_mode_does_not_require_index(tmp_path: Path) -> None:
    report = CoachRagReadinessService(
        _settings(COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=False),
        repository_root=tmp_path,
    ).run()
    assert report.ready is True
    assert report.knowledge_enabled is False


def test_fully_configured_repository_is_ready(tmp_path: Path) -> None:
    settings, repository = _ready_repository(tmp_path)
    report = CoachRagReadinessService(
        settings,
        repository_root=repository,
    ).run(require_enabled=True)
    assert report.ready is True
    assert report.exit_code == ReadinessExitCode.READY
    assert {item.code for item in report.checks} >= {
        "CORPUS_VALID",
        "INDEX_MATCHES_CONFIGURATION",
        "KNOWLEDGE_TOOL_READ_ONLY",
        "PUBLIC_REFERENCES_CANONICAL",
    }


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"KNOWLEDGE_EMBEDDING_API_KEY": ""},
            ReadinessExitCode.CONFIG_INCOMPLETE,
        ),
        (
            {"COACH_AGENT_BASE_URL": "http://127.0.0.1:9999"},
            ReadinessExitCode.PROVIDER_CONFIGURATION_INVALID,
        ),
        (
            {"COACH_AGENT_KNOWLEDGE_INDEX_ID": "knowledge-" + "a" * 24},
            ReadinessExitCode.INDEX_MISSING_OR_STALE,
        ),
        (
            {"KNOWLEDGE_EMBEDDING_DIMENSIONS": 64},
            ReadinessExitCode.INDEX_MISSING_OR_STALE,
        ),
    ],
)
def test_invalid_configuration_fails_closed(
    tmp_path: Path,
    overrides: dict[str, object],
    expected: ReadinessExitCode,
) -> None:
    settings, repository = _ready_repository(tmp_path)
    changed = settings.model_copy(
        update={
            {
                "KNOWLEDGE_EMBEDDING_API_KEY": "knowledge_embedding_api_key",
                "COACH_AGENT_BASE_URL": "coach_agent_base_url",
                "COACH_AGENT_KNOWLEDGE_INDEX_ID": "coach_agent_knowledge_index_id",
                "KNOWLEDGE_EMBEDDING_DIMENSIONS": "knowledge_embedding_dimensions",
            }[key]: value
            for key, value in overrides.items()
        }
    )
    report = CoachRagReadinessService(
        changed,
        repository_root=repository,
    ).run(require_enabled=True)
    assert report.exit_code == expected


def test_expired_index_and_exposed_runtime_fail(
    tmp_path: Path,
) -> None:
    settings, repository = _ready_repository(tmp_path)
    expired = CoachRagReadinessService(
        settings,
        repository_root=repository,
        now=datetime.now(timezone.utc) + timedelta(days=31),
    ).run(require_enabled=True)
    assert expired.exit_code == ReadinessExitCode.INDEX_MISSING_OR_STALE

    (repository / ".gitignore").write_text("", encoding="utf-8")
    exposed = CoachRagReadinessService(
        settings,
        repository_root=repository,
    ).run(require_enabled=True)
    assert exposed.exit_code == ReadinessExitCode.SECURITY_BOUNDARY_FAILED


def test_json_output_contains_modes_but_not_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(
        COACH_AGENT_ENABLED=False,
        COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=False,
    )
    monkeypatch.setattr(
        "scripts.check_coach_rag_readiness.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "scripts.check_coach_rag_readiness.REPOSITORY_ROOT",
        tmp_path,
    )
    assert main(["--json"]) == 0
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert payload["chat_provider"] == "openai-compatible"
    assert "fictional-chat-secret" not in raw
    assert "fictional-embedding-secret" not in raw
    assert "api_key" not in raw.lower()


def test_bm25_strategy_is_ready_without_embedding_configuration(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    shutil.copytree(source_root / "knowledge", tmp_path / "knowledge")
    (tmp_path / ".gitignore").write_text("var/knowledge_bm25_indexes/\n", encoding="utf-8")
    KnowledgeCorpusService(repository_root=tmp_path).build(force=True)
    index = Bm25IndexService(repository_root=tmp_path).build()
    settings = _settings(
        KNOWLEDGE_EMBEDDING_ENABLED=False,
        KNOWLEDGE_EMBEDDING_API_KEY="",
        KNOWLEDGE_RETRIEVAL_STRATEGY="bm25",
        COACH_AGENT_KNOWLEDGE_BM25_INDEX_ID=index.index_id,
    )
    report = CoachRagReadinessService(settings, repository_root=tmp_path).run(require_enabled=True)
    assert report.ready is True
    assert "EMBEDDING_NOT_REQUIRED" in {item.code for item in report.checks}
