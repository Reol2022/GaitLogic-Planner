import socket
import subprocess
import sys

from server.agent.evaluation.fixtures import EVALUATION_FIXTURES
from server.agent.evaluation.loader import load_evaluation_cases
from server.agent.evaluation.runner import CoachAgentEvaluationRunner


def test_all_32_fictional_cases_load_and_cover_required_categories() -> None:
    cases = load_evaluation_cases("evaluation/coach_agent/cases_v1.jsonl")
    assert len(cases) == 32
    assert len({case.case_id for case in cases}) == 32
    assert {case.fixture for case in cases}.issubset(EVALUATION_FIXTURES)
    counts = {}
    for case in cases:
        counts[case.category.value] = counts.get(case.category.value, 0) + 1
    assert counts == {
        "today_recommendation": 10,
        "explain_runner_state": 6,
        "general_training_question": 4,
        "unknown_data": 4,
        "degraded": 4,
        "security": 4,
    }


def test_complete_case_set_passes_without_network(monkeypatch) -> None:
    def deny_network(*_args, **_kwargs):
        raise AssertionError("evaluation must not access the network")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    cases = load_evaluation_cases("evaluation/coach_agent/cases_v1.jsonl")
    report = CoachAgentEvaluationRunner().run(cases)
    assert report.summary.total_cases == 32
    assert report.summary.passed_cases == 32


def test_cli_success_and_filter_failure_exit_codes() -> None:
    success = subprocess.run(
        [sys.executable, "scripts/evaluate_coach_agent.py", "--case-id", "today_001", "--no-write"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    failure = subprocess.run(
        [sys.executable, "scripts/evaluate_coach_agent.py", "--case-id", "missing_case", "--no-write"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert success.returncode == 0
    assert failure.returncode == 2
