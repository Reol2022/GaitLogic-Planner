from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from server.knowledge_retrieval.errors import KnowledgePathError


BLOCKED_DIRECTORY_NAMES = {
    ".git",
    "dist",
    "node_modules",
    "uploads",
    "upload",
    "__pycache__",
}


def as_posix_relative(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise KnowledgePathError("Path is outside the configured knowledge root.") from exc
    return PurePosixPath(relative).as_posix()


def ensure_within_root(path: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise KnowledgePathError("Path is outside the configured knowledge root.") from exc
    return resolved_path


def safe_output_path(output: Path, repository_root: Path) -> Path:
    if output.is_absolute():
        raise KnowledgePathError("Output path must be repository-relative.")
    if ".." in output.parts:
        raise KnowledgePathError("Output path cannot traverse outside the repository.")
    resolved = (repository_root / output).resolve()
    ensure_within_root(resolved, repository_root)
    return resolved


@dataclass(frozen=True)
class CorpusPaths:
    repository_root: Path
    knowledge_root: Path
    documents_dir: Path
    sources_dir: Path
    taxonomy_dir: Path
    rules_dir: Path
    manifests_dir: Path

    @classmethod
    def create(
        cls,
        knowledge_root: Path,
        *,
        repository_root: Path | None = None,
    ) -> CorpusPaths:
        resolved_knowledge = knowledge_root.resolve()
        resolved_repository = (repository_root or resolved_knowledge.parent).resolve()
        ensure_within_root(resolved_knowledge, resolved_repository)
        return cls(
            repository_root=resolved_repository,
            knowledge_root=resolved_knowledge,
            documents_dir=resolved_knowledge / "documents",
            sources_dir=resolved_knowledge / "sources",
            taxonomy_dir=resolved_knowledge / "taxonomy",
            rules_dir=resolved_knowledge / "rules",
            manifests_dir=resolved_knowledge / "manifests",
        )

    def relative(self, path: Path) -> str:
        return as_posix_relative(path, self.knowledge_root)
