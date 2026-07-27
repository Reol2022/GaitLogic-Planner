from __future__ import annotations

from pathlib import Path

from server.knowledge_retrieval.evaluation.report import (
    report_to_markdown,
    write_report,
)
from server.knowledge_retrieval.evaluation.runner import (
    TrainingKnowledgeEvaluationRunner,
)


def test_reporter_writes_json_and_markdown_without_raw_answers(tmp_path: Path) -> None:
    report = TrainingKnowledgeEvaluationRunner(repository_root=Path.cwd()).run_rag(
        dataset_path=Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json")
    )
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    write_report(report, json_path=json_path, markdown_path=markdown_path)
    assert json_path.exists()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Raw answers saved: **No**" in markdown
    assert report.result_hash in markdown
    assert "API keys are never" in report_to_markdown(report)
