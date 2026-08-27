from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import re
import subprocess
import tomllib

from fastapi import APIRouter

from planner_core.config import get_settings
from server.common.response import HealthResponse, VersionResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@lru_cache(maxsize=1)
def _app_version() -> str:
    source_manifest = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if source_manifest.is_file():
        try:
            project = tomllib.loads(source_manifest.read_text(encoding="utf-8")).get(
                "project", {}
            )
            declared = str(project.get("version", "")).strip()
            if declared:
                return declared
        except (OSError, tomllib.TOMLDecodeError):
            pass
    try:
        return version("gaitlogic-planner")
    except PackageNotFoundError:
        return "0.16.3"


@lru_cache(maxsize=1)
def _git_commit() -> str:
    configured = os.getenv("GAITLOGIC_GIT_COMMIT", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{7,40}", configured):
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True,
            check=True,
            text=True,
            timeout=1,
        )
        detected = result.stdout.strip().lower()
        return detected if re.fullmatch(r"[0-9a-f]{7,40}", detected) else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@router.get("/system/version", response_model=VersionResponse)
def system_version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        app_version=_app_version(),
        git_commit=_git_commit(),
        environment=settings.app_env,
        build_time=os.getenv("GAITLOGIC_BUILD_TIME") or None,
    )
