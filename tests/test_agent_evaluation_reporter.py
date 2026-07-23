import json
from pathlib import Path

from server.agent.evaluation.loader import load_evaluation_cases
from server.agent.evaluation.reporter import report_to_markdown, write_report
from server.agent.evaluation.runner import CoachAgentEvaluationRunner


def small_report():
    cases = load_evaluation_cases("evaluation/coach_agent/cases_v1.jsonl")[:2]
    return CoachAgentEvaluationRunner().run(cases)


def test_json_and_markdown_reports_are_reproducible_and_safe(tmp_path: Path) -> None:
    report = small_report()
    json_path = tmp_path / "result.json"
    markdown_path = tmp_path / "result.md"
    write_report(report, json_path=json_path, markdown_path=markdown_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["evaluation_version"] == "coach-agent-eval-1.0.0"
    assert "Required Tool Recall" in markdown
    serialized = json_path.read_text(encoding="utf-8").lower()
    for forbidden in (
        "api_key",
        "system_instructions",
        "conversation_context",
        "tool_outputs",
        "provider_response",
        "database_url",
    ):
        assert forbidden not in serialized


def test_markdown_lists_failed_assertions() -> None:
    report = small_report()
    report.cases[0].passed = False
    report.cases[0].assertions[0].passed = False
    markdown = report_to_markdown(report)
    assert report.cases[0].case_id in markdown
    assert report.cases[0].assertions[0].code in markdown
