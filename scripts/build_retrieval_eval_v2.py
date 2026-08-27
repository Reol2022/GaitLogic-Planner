#!/usr/bin/env python3
"""Build the reviewed retrieval-v2 fixture and its semantic audit report.

The labels below are human-authored from query intent and document content.  The
current ranking is used only to populate the audit's `Current Top4` column; it
never creates or changes a relevance label.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.knowledge_retrieval.embeddings.deterministic import DeterministicEmbeddingProvider
from server.knowledge_retrieval.evaluation.datasets import canonical_dataset_hash
from server.knowledge_retrieval.evaluation.runner import TrainingKnowledgeEvaluationRunner
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.manifest import load_manifest


V1_FIXTURE = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v1.json"
V2_FIXTURE = ROOT / "docs/rag/evaluation/cases/retrieval-eval-v2.json"
V1_MANIFEST = ROOT / "docs/evaluation/baselines/retrieval-v1-corpus-manifest.json"
AUDIT_REPORT = ROOT / "docs/evaluation/retrieval-evaluation-v2-semantic-audit.md"
CURRENT_MANIFEST = ROOT / "knowledge/manifests/corpus-v1.json"
V1_CORPUS_COMMIT = "04f4e5b795e0d19fea8a9916b73b4d21fa34de59"


# Additional legitimate evidence beyond the original twelve GaitLogic documents.
# A grade of 2 means directly relevant supporting evidence; grade 1 means a valid
# secondary perspective.  Original v1 labels retain grade 3.
REVIEWED_ADDITIONS: dict[str, dict[str, int]] = {
    "ret_single_001": {"daniels-training-principles": 2, "daniels-training-load-variables": 2, "intensity-density-management": 2, "threshold-control-signals": 1},
    "ret_single_002": {"daniels-rest-and-return-to-running": 1, "recovery-week-principles": 1},
    "ret_single_003": {"daniels-marathon-2q-plan": 2, "daniels-marathon-cycles": 1, "daniels-training-load-variables": 1},
    "ret_single_004": {"daniels-training-load-variables": 2, "daniels-training-stress-recording": 1, "daniels-marathon-2q-plan": 1},
    "ret_single_005": {"daniels-interval-purpose": 2, "daniels-cruise-intervals": 2, "daniels-repetition-training": 1, "daniels-hard-running-short-intervals": 1},
    "ret_single_006": {"daniels-interval-purpose": 2, "daniels-hard-running-short-intervals": 2, "daniels-repetition-training": 2},
    "ret_single_007": {"daniels-marathon-2q-plan": 2, "daniels-phase-length-adjustment": 1},
    "ret_single_008": {"daniels-long-run-progression": 2, "daniels-easy-running": 1, "daniels-training-principles": 1},
    "ret_single_009": {"daniels-planned-unplanned-rest": 1, "daniels-rest-and-return-to-running": 1},
    "ret_single_011": {"daniels-four-season-phases": 2, "daniels-phase-length-adjustment": 2, "daniels-season-phasing": 2},
    "ret_single_012": {"daniels-four-season-phases": 2, "daniels-phase-length-adjustment": 2, "daniels-season-phasing": 2},
    "ret_single_013": {"daniels-four-season-phases": 2, "daniels-5k-10k-training": 1, "daniels-marathon-final-preparation": 1},
    "ret_single_014": {"daniels-four-season-phases": 1, "daniels-marathon-final-preparation": 1},
    "ret_single_015": {"daniels-long-run-progression": 2, "daniels-return-volume-adjustment": 2, "daniels-training-load-variables": 1},
    "ret_single_016": {"daniels-long-run-progression": 2, "daniels-training-stress-recording": 1, "daniels-training-load-variables": 1},
    "ret_single_017": {"daniels-training-principles": 2, "daniels-planned-unplanned-rest": 2, "daniels-easy-running": 1},
    "ret_single_018": {"daniels-planned-unplanned-rest": 2, "daniels-rest-and-return-to-running": 2, "daniels-easy-running": 1},
    "ret_single_021": {"daniels-threshold-purpose": 2, "daniels-performance-variables": 2, "daniels-heart-rate-context": 1},
    "ret_single_022": {"daniels-threshold-purpose": 2, "daniels-performance-variables": 2, "daniels-cruise-intervals": 1},
    "ret_single_023": {"daniels-marathon-2q-plan": 1, "daniels-half-marathon-training": 1},
    "ret_single_024": {"daniels-marathon-2q-plan": 1, "daniels-cruise-intervals": 1, "long-run-placement": 2},
    "ret_single_025": {"daniels-training-principles": 1, "daniels-training-load-variables": 1},
    "ret_single_026": {"daniels-training-load-variables": 2, "daniels-marathon-2q-plan": 1},
    "ret_single_027": {"daniels-four-season-phases": 2, "daniels-marathon-final-preparation": 1},
    "ret_single_029": {"daniels-threshold-purpose": 2, "daniels-performance-variables": 2, "daniels-heart-rate-context": 1},
    "ret_single_030": {"daniels-long-run-progression": 2, "daniels-training-load-variables": 1, "intensity-density-management": 2},
    "ret_multi_001": {"daniels-training-principles": 1, "daniels-training-load-variables": 2},
    "ret_multi_002": {"daniels-marathon-2q-plan": 2, "daniels-training-principles": 1},
    "ret_multi_003": {"daniels-training-principles": 2, "daniels-long-run-progression": 1},
    "ret_multi_004": {"daniels-four-season-phases": 2, "daniels-season-phasing": 2, "daniels-marathon-final-preparation": 1},
    "ret_multi_005": {"daniels-threshold-purpose": 2, "daniels-cruise-intervals": 2, "daniels-marathon-2q-plan": 1},
    "ret_multi_006": {"daniels-interval-purpose": 2, "daniels-cruise-intervals": 2, "daniels-marathon-2q-plan": 1},
    "ret_multi_007": {"daniels-marathon-2q-plan": 1, "daniels-training-principles": 1},
    "ret_multi_008": {"daniels-planned-unplanned-rest": 2, "daniels-rest-and-return-to-running": 2},
    "ret_multi_009": {"daniels-long-run-progression": 2, "daniels-training-principles": 1},
    "ret_multi_010": {"daniels-four-season-phases": 1, "daniels-cruise-intervals": 2, "daniels-threshold-purpose": 2},
    "ret_multi_011": {"daniels-long-run-progression": 2, "daniels-training-load-variables": 2, "daniels-interval-purpose": 1},
    "ret_multi_012": {"daniels-four-season-phases": 2, "daniels-marathon-final-preparation": 2},
    "ret_hard_001": {"daniels-easy-running": 2, "daniels-training-principles": 2, "daniels-planned-unplanned-rest": 1},
    "ret_hard_002": {"daniels-threshold-purpose": 3, "daniels-cruise-intervals": 2, "daniels-performance-variables": 1},
    "ret_hard_003": {"daniels-long-run-progression": 3, "daniels-marathon-2q-plan": 1},
    "ret_hard_004": {"daniels-four-season-phases": 2, "daniels-marathon-final-preparation": 1},
    "ret_hard_005": {"daniels-planned-unplanned-rest": 2, "daniels-rest-and-return-to-running": 2},
    "ret_hard_006": {"daniels-four-season-phases": 2, "daniels-phase-length-adjustment": 2, "daniels-season-phasing": 2},
    "ret_hard_008": {"daniels-interval-purpose": 2, "daniels-cruise-intervals": 2, "daniels-hard-running-short-intervals": 2, "daniels-repetition-training": 1},
}


TOPICS: dict[str, list[str]] = {
    "single": ["query-specific training principle", "supporting Daniels evidence"],
    "multi": ["multi-constraint training decision", "supporting Daniels evidence"],
    "hard": ["semantic boundary", "confusable training concepts"],
    "abstain": ["out-of-domain or unauthorized request"],
}


def _write_v1_manifest() -> None:
    result = subprocess.run(
        ["git", "show", f"{V1_CORPUS_COMMIT}:knowledge/manifests/corpus-v1.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    V1_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    V1_MANIFEST.write_bytes(result.stdout)


def _build_v2_fixture() -> dict[str, object]:
    source = json.loads(V1_FIXTURE.read_text(encoding="utf-8"))
    manifest = load_manifest(CURRENT_MANIFEST)
    for case in source["cases"]:
        old = {item["document_id"]: item["relevance"] for item in case.get("relevant_documents", [])}
        old.update(REVIEWED_ADDITIONS.get(case["case_id"], {}))
        case["relevant_documents"] = [
            {"document_id": document_id, "relevance": grade}
            for document_id, grade in sorted(old.items())
        ]
        family = case["case_id"].split("_")[1]
        case["relevant_topics"] = TOPICS[family]
        case["acceptable_sections"] = ["核心原则", "适用场景", "判断条件", "推荐策略", "注意事项", "Evidence"]
        if old:
            case["minimum_relevant_hits"] = 2 if family == "multi" else 1
        case["label_rationale"] = (
            "人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。"
        )
    payload: dict[str, object] = {
        "dataset_version": "retrieval-cases-v2",
        "retrieval_eval_version": "retrieval-evaluation-2.0.0",
        "corpus_version": manifest.corpus_version,
        "corpus_hash": manifest.root_hash,
        "manifest_hash": hashlib.sha256(CURRENT_MANIFEST.read_bytes()).hexdigest(),
        "fixture_version": "retrieval-fixture-2.0.0",
        "content_sha256": "0" * 64,
        "cases": source["cases"],
    }
    payload["content_sha256"] = canonical_dataset_hash(payload)
    V2_FIXTURE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _run_current_v1_fixture():
    with tempfile.TemporaryDirectory(prefix="gaitlogic-retrieval-v2-audit-") as directory:
        temp_root = Path(directory)
        target = temp_root / "knowledge/manifests"
        target.mkdir(parents=True)
        shutil.copyfile(CURRENT_MANIFEST, target / "corpus-v1.json")
        index = KnowledgeIndexService(repository_root=temp_root).build(
            DeterministicEmbeddingProvider(dimensions=64, environment="test")
        )
        return TrainingKnowledgeEvaluationRunner(repository_root=temp_root).run_retrieval(
            dataset_path=V1_FIXTURE,
            provider_factory=lambda: DeterministicEmbeddingProvider(dimensions=64, environment="test"),
            provider_name="deterministic_test",
            model_name="deterministic-sha256-v1",
            mode=EvaluationMode.DENSE_WITH_METADATA,
            index_id=index.manifest.index_id,
        )


def _write_audit(payload: dict[str, object], report) -> None:
    manifest = load_manifest(CURRENT_MANIFEST)
    chunks = {item.chunk_id: item for item in manifest.chunks}
    documents = {item.document_id: item for item in manifest.documents}
    sources = {item.source_id: item for item in manifest.sources}
    cases = {item["case_id"]: item for item in payload["cases"]}
    lines = [
        "# Retrieval Evaluation v2 Semantic Audit",
        "",
        "Labels were reviewed from query intent, document topic, and section semantics. Current Top4 was observed only after labels were authored and did not generate expected results.",
        "",
        f"- Fixture: `{payload['fixture_version']}`",
        f"- Corpus: `{payload['corpus_version']}` / `{payload['corpus_hash']}`",
        f"- Manifest SHA-256: `{payload['manifest_hash']}`",
        "- Ranking audit: deterministic-sha256-v1, 64 dimensions, exact dense, metadata enabled, TopK=4",
        "",
    ]
    for result in report.cases:
        case = cases[result.case_id]
        relevant = {item["document_id"]: item["relevance"] for item in case.get("relevant_documents", [])}
        forbidden = set(case.get("forbidden_document_ids", []))
        old = next(item for item in json.loads(V1_FIXTURE.read_text(encoding="utf-8"))["cases"] if item["case_id"] == result.case_id)
        lines.extend([
            f"## {result.case_id}", "", f"- Query: {case['query']}",
            f"- v1 Expected: {', '.join(x['document_id'] for x in old.get('relevant_documents', [])) or 'ABSTAIN'}",
            "- Current Top4:", "",
            "| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |",
            "|---:|---|---|---|---|---|---|",
        ])
        if not result.ranked_items:
            lines.append("| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |")
        for ranked in result.ranked_items:
            chunk = chunks[ranked.chunk_id]
            document = documents[ranked.document_id]
            source = sources[chunk.source_id]
            if ranked.document_id in forbidden:
                decision, semantic = "FORBIDDEN", "confusable document explicitly excluded"
            elif ranked.document_id in relevant:
                grade = relevant[ranked.document_id]
                decision = "RELEVANT" if grade >= 2 else "PARTIALLY_RELEVANT"
                semantic = f"audited relevance grade {grade}"
            else:
                decision, semantic = "NOT_RELEVANT", "not evidence for the audited query intent"
            lines.append(
                f"| {ranked.rank} | {source.title} | {document.title} (`{ranked.document_id}`) | {chunk.section} | audited label comparison | {semantic} | {decision} |"
            )
        lines.extend(["", "- Decision basis: " + case["label_rationale"], ""])
    AUDIT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    _write_v1_manifest()
    payload = _build_v2_fixture()
    report = _run_current_v1_fixture()
    _write_audit(payload, report)
    print(f"v1_manifest={V1_MANIFEST.relative_to(ROOT)}")
    print(f"v2_fixture={V2_FIXTURE.relative_to(ROOT)}")
    print(f"audit_report={AUDIT_REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
