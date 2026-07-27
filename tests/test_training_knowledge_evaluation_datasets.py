from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.knowledge_retrieval.evaluation.datasets import (
    EvaluationDatasetError,
    load_rag_dataset,
    load_retrieval_dataset,
)


def test_public_datasets_have_required_case_counts_and_unique_ids() -> None:
    retrieval = load_retrieval_dataset(
        Path("docs/rag/evaluation/cases/retrieval-eval-v1.json")
    )
    rag = load_rag_dataset(Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json"))
    assert len(retrieval.cases) == 60
    assert len({item.case_id for item in retrieval.cases}) == 60
    assert len(rag.cases) == 36
    assert len({item.case_id for item in rag.cases}) == 36


def test_dataset_hash_detects_content_change(tmp_path: Path) -> None:
    source = Path("docs/rag/evaluation/cases/retrieval-eval-v1.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["cases"][0]["query"] = "被篡改"
    target = tmp_path / "dataset.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(EvaluationDatasetError, match="SHA-256"):
        load_retrieval_dataset(target)


def test_dataset_contains_no_identity_fields() -> None:
    for path in (
        Path("docs/rag/evaluation/cases/retrieval-eval-v1.json"),
        Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json"),
    ):
        text = path.read_text(encoding="utf-8").lower()
        assert "user_id" not in text
        assert "email" not in text
        assert "phone" not in text
        assert "api_key" not in text
