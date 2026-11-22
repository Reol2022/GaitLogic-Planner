from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from server.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.16.8"


def test_archive_release_commit_uses_manifest(tmp_path, monkeypatch):
    from server.api.routes import health
    monkeypatch.delenv('GAITLOGIC_GIT_COMMIT', raising=False)
    monkeypatch.setattr(health, '__file__', str(tmp_path/'server/api/routes/health.py'))
    (tmp_path/'release-manifest.json').write_text(json.dumps({'git_commit':'a'*40}), encoding='utf-8')
    health._git_commit.cache_clear()
    try:
        assert health._git_commit() == 'a'*40
    finally:
        health._git_commit.cache_clear()


def test_release_version_declarations_are_consistent() -> None:
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    package_json = json.loads(
        (PROJECT_ROOT / "web" / "package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads(
        (PROJECT_ROOT / "web" / "package-lock.json").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["version"] == EXPECTED_VERSION
    assert app.version == EXPECTED_VERSION
    assert app.openapi()["info"]["version"] == EXPECTED_VERSION
    assert package_json["version"] == EXPECTED_VERSION
    assert package_lock["version"] == EXPECTED_VERSION
    assert package_lock["packages"][""]["version"] == EXPECTED_VERSION


def test_frontend_version_is_derived_from_package_json() -> None:
    vite_config = (PROJECT_ROOT / "vite.web.config.mjs").read_text(encoding="utf-8")
    app_config = (PROJECT_ROOT / "web" / "src" / "config" / "app.ts").read_text(
        encoding="utf-8"
    )

    assert "packageJson.version" in vite_config
    assert "__APP_VERSION__" in vite_config
    assert "__APP_VERSION__" in app_config


def test_release_documents_declare_current_version_and_preserve_history() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (PROJECT_ROOT / "README-EN.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "docs" / "更新历史.md").read_text(encoding="utf-8")
    release_notes = (PROJECT_ROOT / "docs" / "release" / "v0.16.3.md").read_text(encoding="utf-8")
    historical_release_notes = (
        PROJECT_ROOT / "docs" / "release" / "v0.16.0.md"
    ).read_text(encoding="utf-8")

    assert "v0.16.8" in readme
    assert "v0.16.8" in readme_en
    assert "## v0.16.8" in changelog
    # The product overview links to history instead of embedding release notes.
    for document in (readme, readme_en):
        assert "docs/更新历史.md" in document
        assert not re.search(r"^#{2,4}\s+v\d+\.\d+", document, re.MULTILINE)
    assert readme.index("## 📘 系统介绍") > readme.index("## 🚀 快速开始")
    assert readme_en.index("## 📘 System Introduction") > readme_en.index("## 🚀 Quick Start")
    assert "## v0.16.3" in changelog
    assert "# GaitLogic Planner v0.16.3" in release_notes
    assert "# GaitLogic Planner v0.16.0" in historical_release_notes
