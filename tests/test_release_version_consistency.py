from __future__ import annotations

import json
import tomllib
from pathlib import Path

from server.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.12.0"


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


def test_release_documents_declare_v0120() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (PROJECT_ROOT / "README-EN.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "docs" / "更新历史.md").read_text(encoding="utf-8")
    release_notes = (
        PROJECT_ROOT / "docs" / "releases" / "v0.12.0-release-notes.md"
    ).read_text(encoding="utf-8")

    assert "v0.12.0" in readme
    assert "v0.12.0" in readme_en
    assert "## v0.12.0" in changelog
    assert "# GaitLogic v0.12.0" in release_notes
