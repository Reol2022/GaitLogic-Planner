from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
import unicodedata

from server.knowledge_retrieval.schemas import (
    ChunkMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
)


CHUNKER_VERSION = "heading-paragraph-v1"
DEFAULT_MAX_CHARS = 1800
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?；;])\s*|(?<=[.!?])\s+")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
SECTION_SLUGS = {
    "适用场景": "applicable-scenarios",
    "核心原则": "core-principles",
    "判断条件": "decision-conditions",
    "推荐策略": "recommended-strategies",
    "注意事项": "cautions",
}


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def estimate_token_count(content: str) -> int:
    """Return a stable approximation, not a provider-specific token count."""

    cjk = len(CJK_RE.findall(content))
    ascii_words = len(ASCII_WORD_RE.findall(content))
    remainder = max(0, len(content) - cjk - sum(map(len, ASCII_WORD_RE.findall(content))))
    return max(1, math.ceil(cjk + ascii_words * 1.3 + remainder / 4))


def _slugify(value: str) -> str:
    if value in SECTION_SLUGS:
        return SECTION_SLUGS[value]
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if slug:
        return slug[:80]
    return f"section-{content_sha256(value)[:10]}"


@dataclass(frozen=True)
class MarkdownSection:
    title: str
    level: int
    path: tuple[str, ...]
    lines: tuple[str, ...]


def parse_markdown_sections(body: str) -> list[MarkdownSection]:
    lines = body.splitlines()
    sections: list[MarkdownSection] = []
    stack: list[tuple[int, str]] = []
    current_title: str | None = None
    current_level = 0
    current_path: tuple[str, ...] = ()
    current_lines: list[str] = []
    in_fence = False

    def flush() -> None:
        if current_title is not None and any(line.strip() for line in current_lines):
            sections.append(
                MarkdownSection(
                    title=current_title,
                    level=current_level,
                    path=current_path,
                    lines=tuple(current_lines),
                )
            )

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            current_lines.append(line)
            continue
        match = None if in_fence else HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_title = title
            current_level = level
            current_path = tuple(item[1] for item in stack)
            current_lines = []
            continue
        if current_title is not None:
            current_lines.append(line)
    flush()
    return sections


def _paragraph_blocks(lines: tuple[str, ...]) -> list[str]:
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        stripped = lines[index].lstrip()
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            block = [lines[index]]
            index += 1
            while index < len(lines):
                block.append(lines[index])
                closing = lines[index].lstrip().startswith(fence)
                index += 1
                if closing:
                    break
            blocks.append("\n".join(block).strip())
            continue
        if LIST_RE.match(lines[index]):
            block = [lines[index]]
            index += 1
            while index < len(lines) and lines[index].strip():
                block.append(lines[index])
                index += 1
            blocks.append("\n".join(block).strip())
            continue
        if "|" in lines[index]:
            block = [lines[index]]
            index += 1
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                block.append(lines[index])
                index += 1
            blocks.append("\n".join(block).strip())
            continue
        block = [lines[index]]
        index += 1
        while index < len(lines) and lines[index].strip():
            if LIST_RE.match(lines[index]) or "|" in lines[index]:
                break
            block.append(lines[index])
            index += 1
        blocks.append("\n".join(block).strip())
    return [block for block in blocks if block]


def _split_long_prose(value: str, max_chars: int) -> list[str]:
    if len(value) <= max_chars:
        return [value]
    sentences = [item.strip() for item in SENTENCE_BOUNDARY_RE.split(value) if item.strip()]
    if len(sentences) <= 1:
        words = value.split()
        if len(words) > 1:
            parts: list[str] = []
            current: list[str] = []
            for word in words:
                candidate = " ".join([*current, word])
                if current and len(candidate) > max_chars:
                    parts.append(" ".join(current))
                    current = [word]
                else:
                    current.append(word)
            if current:
                parts.append(" ".join(current))
            return parts
        # There is no safe semantic boundary in one unbroken token. Preserve it
        # rather than applying an arbitrary fixed-character cut.
        return [value]
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_split_long_prose(sentence, max_chars))
            continue
        candidate = sentence if not current else f"{current}{sentence}"
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _split_section(section: MarkdownSection, max_chars: int) -> list[str]:
    blocks = _paragraph_blocks(section.lines)
    pieces: list[str] = []
    current: list[str] = []
    for block in blocks:
        protected = block.lstrip().startswith(("```", "~~~")) or bool(
            LIST_RE.match(block)
        ) or ("\n" in block and all("|" in line for line in block.splitlines()))
        block_parts = [block] if protected else _split_long_prose(block, max_chars)
        for part in block_parts:
            candidate = "\n\n".join([*current, part])
            if current and len(candidate) > max_chars:
                pieces.append("\n\n".join(current))
                current = [part]
            else:
                current.append(part)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


class DeterministicKnowledgeChunker:
    def __init__(self, *, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        if max_chars < 200:
            raise ValueError("max_chars must be at least 200.")
        self.max_chars = max_chars

    def chunk_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        ordinal = 0
        for section in parse_markdown_sections(document.body):
            section_slug = "-".join(_slugify(item) for item in section.path)
            for piece in _split_section(section, self.max_chars):
                ordinal += 1
                heading = f"{'#' * section.level} {section.title}"
                content = f"{heading}\n\n{piece}".strip()
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=(
                            f"{document.metadata.document_id}#"
                            f"{section_slug}#{ordinal:03d}"
                        ),
                        document_id=document.metadata.document_id,
                        title=document.metadata.title,
                        section=section.title,
                        section_path=list(section.path),
                        category=document.metadata.category,
                        tags=document.metadata.tags,
                        source_id=document.metadata.source_id,
                        knowledge_version=document.metadata.knowledge_version,
                        content=content,
                        content_sha256=content_sha256(content),
                        ordinal=ordinal,
                        char_count=len(content),
                        estimated_token_count=estimate_token_count(content),
                        metadata=ChunkMetadata(
                            evidence_level=document.metadata.evidence_level,
                            source_type=document.metadata.source_type,
                            language=document.metadata.language,
                            status=document.metadata.status,
                            applicable_phases=document.metadata.applicable_phases,
                            document_path=document.relative_path,
                        ),
                    )
                )
        return chunks

    def chunk_documents(
        self,
        documents: list[KnowledgeDocument],
    ) -> list[KnowledgeChunk]:
        chunks = [
            chunk
            for document in sorted(
                documents, key=lambda item: item.metadata.document_id
            )
            for chunk in self.chunk_document(document)
        ]
        return sorted(chunks, key=lambda item: item.chunk_id)
