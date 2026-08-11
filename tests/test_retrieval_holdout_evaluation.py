from __future__ import annotations

import json
from pathlib import Path

from server.knowledge_retrieval.evaluation.datasets import load_retrieval_dataset
from server.knowledge_retrieval.evaluation.holdout import StrategyResult, _pairwise


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "docs/evaluation/datasets/retrieval-holdout-v2.json"
MANIFEST = ROOT / "docs/evaluation/datasets/retrieval-holdout-v2.manifest.json"


def test_holdout_v2_is_frozen_and_separate_from_legacy() -> None:
    dataset = load_retrieval_dataset(DATASET)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert dataset.dataset_version == "retrieval-holdout-v2"
    assert len(dataset.cases) == 40
    assert dataset.content_sha256 == manifest["content_sha256"]
    assert all(case.label_rationale for case in dataset.cases)
    assert {case.case_id for case in dataset.cases}.isdisjoint(
        {f"ret_{index:03d}" for index in range(1, 61)}
    )


def test_pairwise_comparison_reports_recovery_and_regression() -> None:
    left = StrategyResult("COMPLETED", {}, {"ret_holdout_001": True, "ret_holdout_002": False})
    right = StrategyResult("COMPLETED", {}, {"ret_holdout_001": False, "ret_holdout_002": True})
    report = _pairwise(left, right)
    assert report["recovered_cases"] == ["ret_holdout_002"]
    assert report["regressed_cases"] == ["ret_holdout_001"]


def test_frozen_config_keeps_fixed_v016_parameters() -> None:
    frozen = json.loads((ROOT / "docs/evaluation/retrieval-v016-frozen-config.json").read_text(encoding="utf-8"))
    assert frozen["top_k"] == 4
    assert frozen["hybrid_rrf"]["dense_candidate_depth"] == 8
    assert frozen["hybrid_rrf"]["bm25_candidate_depth"] == 8
    assert frozen["hybrid_rrf"]["rrf_k"] == 60
    assert frozen["rerank"]["instruction_version"] == "gaitlogic_rerank_v1"
