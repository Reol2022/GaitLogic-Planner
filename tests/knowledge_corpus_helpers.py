from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SECTIONS = """## 适用场景

适用于虚构测试场景。

## 核心原则

保持训练内容可解释。

## 判断条件

- 训练数据存在。
- 数据质量可用。

## 推荐策略

采用保守、可复核的建议。

## 注意事项

不构成医疗建议。
"""


def source_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_id": "test-original-source",
        "title": "Original Test Source",
        "source_type": "ORIGINAL_CONTENT",
        "authors": ["GaitLogic Tests"],
        "publication_year": 2026,
        "license_status": "ORIGINAL",
        "usage_policy": "ORIGINAL_CONTENT",
    }
    record.update(overrides)
    return record


def document_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "document_id": "test-training-document",
        "title": "虚构训练知识",
        "category": "GENERAL",
        "tags": ["test"],
        "applicable_phases": ["BASE"],
        "source_id": "test-original-source",
        "source_type": "ORIGINAL_CONTENT",
        "evidence_level": "INTERNAL",
        "knowledge_version": "1.0.0",
        "language": "zh-CN",
        "status": "ACTIVE",
        "reviewed_at": "2026-07-23",
    }
    metadata.update(overrides)
    return metadata


def write_corpus(
    repository_root: Path,
    *,
    root_name: str = "knowledge",
    metadata: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
    body: str = SECTIONS,
    filename: str = "document.md",
) -> Path:
    root = repository_root / root_name
    documents = root / "documents"
    source_dir = root / "sources"
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    documents.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    source_payload = {"sources": sources or [source_record()]}
    (source_dir / "sources.yaml").write_text(
        yaml.safe_dump(source_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    front_matter = yaml.safe_dump(
        metadata or document_metadata(),
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    (documents / filename).write_text(
        f"---\n{front_matter}\n---\n\n{body}",
        encoding="utf-8",
    )
    return root
