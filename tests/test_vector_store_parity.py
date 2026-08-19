from __future__ import annotations

import importlib.util

import pytest

from scripts.evaluate_vector_store_parity import run_parity


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("qdrant_client") is None,
    reason="qdrant-client is an optional dependency",
)


def test_qdrant_preserves_existing_exact_dense_retrieval_baseline() -> None:
    report = run_parity()
    assert report["case_count"] == 60
    assert report["exact"]["passed"] + report["exact"]["failed"] == report["case_count"]
    assert report["qdrant"] == report["exact"]
    assert report["ranking_mismatch_case_ids"] == []
    assert report["parity"] is True
