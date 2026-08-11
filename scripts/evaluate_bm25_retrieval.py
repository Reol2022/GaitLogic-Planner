"""Generate the public, deterministic Dense/BM25 comparison report."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider  # noqa: E402
from server.knowledge_retrieval.evaluation.bm25_comparison import run_bm25_comparison  # noqa: E402
from server.knowledge_retrieval.evaluation.runner import TrainingKnowledgeEvaluationRunner  # noqa: E402
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode  # noqa: E402
from server.knowledge_retrieval.index_service import KnowledgeIndexService  # noqa: E402

DATASET = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"
REPORT_DIRECTORY = ROOT / "docs/evaluation/reports"


def _markdown(report: dict[str, object]) -> str:
    dense, bm25, overlap = report["dense"], report["bm25"], report["overlap"]
    def rows(metrics):
        return "\n".join(f"| {key} | {value:.4f} |" for key, value in sorted(metrics.items()))
    return f"""# Dense 与 BM25 Retrieval 对比 v1

## 范围

同一公开 60 条 Retrieval Dataset、同一 Corpus、相同 metadata filters 与 `top_k=4`。Dense 继续使用既有 deterministic embedding baseline；BM25 是独立、本地、无网络依赖的 `bm25_v1` 索引。本报告不包含 query 正文、chunk 正文、向量或私有评测资产。

## Dense

- Cases: {dense['case_count']}

| Metric | Result |
| --- | ---: |
{rows(dense['metrics'])}

## BM25

- Cases: {bm25['case_count']}
- Index: `{bm25['index_id']}`

| Metric | Result |
| --- | ---: |
{rows(bm25['metrics'])}

## Overlap

| Group | Cases |
| --- | ---: |
| Dense only success | {len(overlap['dense_only_success'])} |
| BM25 only success | {len(overlap['bm25_only_success'])} |
| Both success | {len(overlap['both_success'])} |
| Both fail | {len(overlap['both_fail'])} |

BM25 是否优于 Dense 不能由单一通过率断言；v0.16-C 应只在这些互补性、排序和失败类型证据基础上评估 Hybrid fusion。
"""


def main() -> int:
    # Build both derived indexes in a disposable repository.  The checked-in
    # corpus and public dataset stay read-only and no runtime index is committed.
    with tempfile.TemporaryDirectory(prefix="gaitlogic-bm25-comparison-") as raw:
        sandbox = Path(raw)
        target = sandbox / "knowledge/manifests"
        target.mkdir(parents=True)
        shutil.copyfile(ROOT / "knowledge/manifests/corpus-v1.json", target / "corpus-v1.json")
        service = KnowledgeIndexService(repository_root=sandbox, index_root=Path("var/dense"))
        dense_index = service.build(DeterministicEmbeddingProvider(dimensions=64, environment="test"))
        runner = TrainingKnowledgeEvaluationRunner(repository_root=sandbox, index_root=Path("var/dense"))
        dense = runner.run_retrieval(dataset_path=DATASET, provider_factory=lambda: DeterministicEmbeddingProvider(dimensions=64, environment="test"), provider_name="deterministic_test", model_name="deterministic-sha256-v1", mode=EvaluationMode.DENSE_WITH_METADATA, index_id=dense_index.manifest.index_id)
        report = run_bm25_comparison(repository_root=sandbox, dataset_path=DATASET, dense_report=dense)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (REPORT_DIRECTORY / "retrieval-bm25-comparison-v1.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (REPORT_DIRECTORY / "retrieval-bm25-comparison-v1.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"dense_pass": dense.case_count - len(dense.failure_case_ids), "bm25_pass": report["bm25"]["case_count"] - len(report["bm25"]["failure_case_ids"]), "overlap": {key: len(value) for key, value in report["overlap"].items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
