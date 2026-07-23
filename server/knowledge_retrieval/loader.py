from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from pydantic import ValidationError
import yaml

from server.knowledge_retrieval.errors import KnowledgeLoadError, KnowledgePathError
from server.knowledge_retrieval.paths import (
    BLOCKED_DIRECTORY_NAMES,
    CorpusPaths,
    ensure_within_root,
)
from server.knowledge_retrieval.schemas import (
    KnowledgeDocument,
    KnowledgeDocumentMetadata,
    KnowledgeSource,
    KnowledgeSourceDefinition,
)


MAX_KNOWLEDGE_FILE_BYTES = 512 * 1024
REQUIRED_SECTIONS = (
    "适用场景",
    "核心原则",
    "判断条件",
    "推荐策略",
    "注意事项",
)
TEMPORARY_SUFFIXES = (".tmp", ".temp", ".bak", ".swp", "~")
SCRIPT_PATTERN = re.compile(r"<\s*script\b", re.IGNORECASE)
REMOTE_INCLUDE_PATTERNS = (
    re.compile(r"!\s*INCLUDE\s+[\"']?https?://", re.IGNORECASE),
    re.compile(r"\{\{\s*(?:include|import)\s+[\"']?https?://", re.IGNORECASE),
)
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _is_ignored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    for part in relative.parts:
        if part.startswith(".") or part in BLOCKED_DIRECTORY_NAMES:
            return True
    lowered = path.name.lower()
    return lowered.startswith(("~", "#")) or lowered.endswith(TEMPORARY_SUFFIXES)


def _safe_files(root: Path, suffixes: set[str]) -> list[Path]:
    if not root.exists():
        raise KnowledgeLoadError(f"Required knowledge directory is missing: {root.name}")
    if not root.is_dir():
        raise KnowledgeLoadError(f"Knowledge path is not a directory: {root.name}")
    files: list[Path] = []
    for path in root.rglob("*"):
        if _is_ignored(path, root):
            continue
        if path.is_symlink():
            try:
                ensure_within_root(path, root)
            except KnowledgePathError as exc:
                raise KnowledgeLoadError(
                    f"Symlink escapes the configured knowledge directory: {path.name}"
                ) from exc
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        ensure_within_root(path, root)
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _read_utf8(path: Path, *, display_path: str) -> tuple[str, bytes]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise KnowledgeLoadError(f"{display_path}: cannot inspect file.") from exc
    if size > MAX_KNOWLEDGE_FILE_BYTES:
        raise KnowledgeLoadError(
            f"{display_path}: file exceeds {MAX_KNOWLEDGE_FILE_BYTES} bytes."
        )
    try:
        raw = path.read_bytes()
        return raw.decode("utf-8"), raw
    except UnicodeDecodeError as exc:
        raise KnowledgeLoadError(f"{display_path}: file must be UTF-8.") from exc
    except OSError as exc:
        raise KnowledgeLoadError(f"{display_path}: cannot read file.") from exc


def _parse_front_matter(text: str, display_path: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines()
    if not lines or lines[0].strip() != "---":
        raise KnowledgeLoadError(f"{display_path}: missing YAML Front Matter.")
    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise KnowledgeLoadError(f"{display_path}: unterminated YAML Front Matter.")
    front_matter = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip()
    try:
        payload = yaml.safe_load(front_matter)
    except yaml.YAMLError as exc:
        raise KnowledgeLoadError(f"{display_path}: invalid YAML Front Matter.") from exc
    if not isinstance(payload, dict):
        raise KnowledgeLoadError(f"{display_path}: Front Matter must be an object.")
    if not body:
        raise KnowledgeLoadError(f"{display_path}: document body cannot be empty.")
    return payload, body


def _validate_document_content(body: str, display_path: str) -> None:
    if SCRIPT_PATTERN.search(body):
        raise KnowledgeLoadError(f"{display_path}: HTML script is not allowed.")
    if any(pattern.search(body) for pattern in REMOTE_INCLUDE_PATTERNS):
        raise KnowledgeLoadError(f"{display_path}: remote includes are not allowed.")
    headings = {match.group(1).strip() for match in HEADING_PATTERN.finditer(body)}
    missing = [section for section in REQUIRED_SECTIONS if section not in headings]
    if missing:
        raise KnowledgeLoadError(
            f"{display_path}: missing required sections: {', '.join(missing)}."
        )


def _records_from_source_payload(payload: Any, display_path: str) -> list[dict[str, Any]]:
    records: Any
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("sources"), list):
        if set(payload) != {"sources"}:
            raise KnowledgeLoadError(
                f"{display_path}: source file contains unknown top-level fields."
            )
        records = payload["sources"]
    else:
        raise KnowledgeLoadError(
            f"{display_path}: expected a list or an object containing sources."
        )
    if not all(isinstance(item, dict) for item in records):
        raise KnowledgeLoadError(f"{display_path}: every source must be an object.")
    return records


class KnowledgeCorpusLoader:
    def __init__(self, paths: CorpusPaths) -> None:
        self.paths = paths

    def load_sources(self) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        seen: set[str] = set()
        for path in _safe_files(self.paths.sources_dir, {".yaml", ".yml"}):
            relative = self.paths.relative(path)
            text, _ = _read_utf8(path, display_path=relative)
            try:
                payload = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise KnowledgeLoadError(f"{relative}: invalid source YAML.") from exc
            for index, record in enumerate(
                _records_from_source_payload(payload, relative)
            ):
                try:
                    definition = KnowledgeSourceDefinition.model_validate(record)
                except ValidationError as exc:
                    raise KnowledgeLoadError(
                        f"{relative}: source[{index}] validation failed: {exc}"
                    ) from exc
                if definition.source_id in seen:
                    raise KnowledgeLoadError(
                        f"Duplicate source_id: {definition.source_id}."
                    )
                seen.add(definition.source_id)
                record_hash = sha256_bytes(
                    canonical_json(
                        definition.model_dump(mode="json", exclude_none=True)
                    ).encode("utf-8")
                )
                sources.append(
                    KnowledgeSource(
                        **definition.model_dump(),
                        relative_path=relative,
                        record_sha256=record_hash,
                    )
                )
        return sorted(sources, key=lambda item: item.source_id)

    def load_documents(
        self,
        sources: Iterable[KnowledgeSource],
    ) -> list[KnowledgeDocument]:
        source_by_id = {source.source_id: source for source in sources}
        documents: list[KnowledgeDocument] = []
        seen: set[str] = set()
        for path in _safe_files(self.paths.documents_dir, {".md"}):
            relative = self.paths.relative(path)
            text, raw = _read_utf8(path, display_path=relative)
            payload, body = _parse_front_matter(text, relative)
            try:
                metadata = KnowledgeDocumentMetadata.model_validate(payload)
            except ValidationError as exc:
                raise KnowledgeLoadError(
                    f"{relative}: Front Matter validation failed: {exc}"
                ) from exc
            if metadata.document_id in seen:
                raise KnowledgeLoadError(
                    f"Duplicate document_id: {metadata.document_id}."
                )
            seen.add(metadata.document_id)
            source = source_by_id.get(metadata.source_id)
            if source is None:
                raise KnowledgeLoadError(
                    f"{relative}: source_id does not exist: {metadata.source_id}."
                )
            if source.source_type != metadata.source_type:
                raise KnowledgeLoadError(
                    f"{relative}: source_type does not match source record."
                )
            _validate_document_content(body, relative)
            documents.append(
                KnowledgeDocument(
                    metadata=metadata,
                    body=body,
                    relative_path=relative,
                    file_sha256=sha256_bytes(raw),
                )
            )
        return sorted(documents, key=lambda item: item.metadata.document_id)

    def load(self) -> tuple[list[KnowledgeDocument], list[KnowledgeSource]]:
        sources = self.load_sources()
        documents = self.load_documents(sources)
        return documents, sources
