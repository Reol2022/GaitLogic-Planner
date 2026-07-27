from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.evaluation.datasets import load_retrieval_dataset
from server.knowledge_retrieval.evaluation.lexical_baseline import (
    LexicalBm25Baseline,
    tokenize,
)
from server.knowledge_retrieval.manifest import load_manifest


def test_chinese_tokenization_is_deterministic() -> None:
    assert tokenize("阈值训练 Threshold") == tokenize("阈值训练 Threshold")
    assert "threshold" in tokenize("阈值训练 Threshold")


def test_bm25_respects_category_filters_and_stable_order() -> None:
    corpus = load_manifest(Path("knowledge/manifests/corpus-v1.json"))
    dataset = load_retrieval_dataset(
        Path("docs/rag/evaluation/cases/retrieval-eval-v1.json")
    )
    case = next(item for item in dataset.cases if item.case_id == "ret_single_022")
    baseline = LexicalBm25Baseline(corpus)
    first = baseline.search(case)
    second = baseline.search(case)
    assert first == second
    assert first
    assert all(
        next(chunk for chunk in corpus.chunks if chunk.chunk_id == item.chunk_id).category.value
        == "THRESHOLD"
        for item in first
    )


def test_bm25_is_not_registered_as_a_product_tool() -> None:
    from server.agent.tools.factory import COACH_AGENT_TOOL_NAMES

    assert "lexical_bm25" not in COACH_AGENT_TOOL_NAMES
