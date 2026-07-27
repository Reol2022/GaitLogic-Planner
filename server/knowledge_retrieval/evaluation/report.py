from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from server.knowledge_retrieval.evaluation.schemas import (
    TrainingKnowledgeEvaluationReport,
)


def report_to_markdown(report: TrainingKnowledgeEvaluationReport) -> str:
    provider_kind = "real provider" if report.real_provider else "offline/fake provider"
    rows = "\n".join(
        f"| {name} | {value:.4f} |" for name, value in sorted(report.metrics.items())
    )
    failures = (
        ", ".join(report.failure_case_ids) if report.failure_case_ids else "None"
    )
    limitations = "\n".join(f"- {item}" for item in report.limitations) or "- None"
    return f"""# Training Knowledge {report.evaluation_kind.title()} Evaluation v1

## Scope

- Dataset: `{report.dataset_version}`
- Dataset SHA-256: `{report.dataset_sha256}`
- Corpus root: `{report.corpus_root_hash}`
- Index: `{report.index_id or "not used"}`
- Provider/model: `{report.provider}` / `{report.model}`
- Execution: {provider_kind}
- Mode: `{report.mode.value}`
- Cases: {report.case_count}
- Raw answers saved: **No**
- Generated at: {report.generated_at}
- Result hash: `{report.result_hash}`

## Metrics

| Metric | Result |
| --- | ---: |
{rows}

## Failed cases

{failures}

## Known limitations

{limitations}

## Reproduce

Run `python scripts/evaluate_training_knowledge.py {report.evaluation_kind}` from
the repository root. Real-provider runs require server-side environment settings;
API keys are never command-line arguments or report fields.

## Safety boundary

The report contains case identifiers, ranked chunk/document identifiers, scores,
safe validation codes, and aggregate metrics only. It excludes raw provider
answers, prompts, contexts, tool results, vectors, credentials, and identities.
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_report(
    report: TrainingKnowledgeEvaluationReport,
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    _atomic_write(
        json_path,
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    _atomic_write(markdown_path, report_to_markdown(report))
