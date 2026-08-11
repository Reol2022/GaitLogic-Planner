"""Compare Exact Cosine and Qdrant against the unchanged public retrieval set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.knowledge_retrieval.embeddings.deterministic import (  # noqa: E402
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.evaluation.runner import (  # noqa: E402
    TrainingKnowledgeEvaluationRunner,
)
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode  # noqa: E402
from server.knowledge_retrieval.index_service import KnowledgeIndexService  # noqa: E402


DATASET = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"


def _run_store(root: Path, *, vector_store: str) -> dict[str, Any]:
    manifest_target = root / "knowledge/manifests"
    manifest_target.mkdir(parents=True)
    shutil.copyfile(
        ROOT / "knowledge/manifests/corpus-v1.json",
        manifest_target / "corpus-v1.json",
    )
    index_root = Path("var") / vector_store
    service = KnowledgeIndexService(
        repository_root=root,
        index_root=index_root,
        vector_store=vector_store,
    )
    build = service.build(DeterministicEmbeddingProvider(dimensions=64, environment="test"))
    runner = TrainingKnowledgeEvaluationRunner(
        repository_root=root,
        index_root=index_root,
        vector_store=vector_store,
    )
    report = runner.run_retrieval(
        dataset_path=DATASET,
        provider_factory=lambda: DeterministicEmbeddingProvider(
            dimensions=64,
            environment="test",
        ),
        provider_name="deterministic_test",
        model_name="deterministic-sha256-v1",
        mode=EvaluationMode.DENSE_WITH_METADATA,
        index_id=build.manifest.index_id,
    )
    return report.model_dump(mode="json")


def run_parity() -> dict[str, Any]:
    """Run only fictional offline data and return safe aggregate/report ids."""

    with tempfile.TemporaryDirectory(prefix="gaitlogic-vector-parity-") as raw:
        root = Path(raw)
        exact = _run_store(root / "exact", vector_store="exact")
        qdrant = _run_store(root / "qdrant", vector_store="qdrant")
    exact_rankings = {
        case["case_id"]: [item["chunk_id"] for item in case["ranked_items"]]
        for case in exact["cases"]
    }
    qdrant_rankings = {
        case["case_id"]: [item["chunk_id"] for item in case["ranked_items"]]
        for case in qdrant["cases"]
    }
    mismatches = sorted(
        case_id
        for case_id in exact_rankings
        if exact_rankings[case_id] != qdrant_rankings.get(case_id)
    )
    return {
        "dataset": "public_retrieval_eval_v1",
        "case_count": len(exact_rankings),
        "exact": {
            "passed": sum(1 for case in exact["cases"] if case["passed"]),
            "failed": sum(1 for case in exact["cases"] if not case["passed"]),
            "failure_case_ids": exact["failure_case_ids"],
        },
        "qdrant": {
            "passed": sum(1 for case in qdrant["cases"] if case["passed"]),
            "failed": sum(1 for case in qdrant["cases"] if not case["passed"]),
            "failure_case_ids": qdrant["failure_case_ids"],
        },
        "ranking_mismatch_case_ids": mismatches,
        "parity": not mismatches
        and exact["failure_case_ids"] == qdrant["failure_case_ids"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate dense-retrieval parity without changing public cases."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_parity()
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.is_absolute() or ".." in args.output.parts:
            parser.error("--output must be repository-relative")
        target = ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if result["parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
