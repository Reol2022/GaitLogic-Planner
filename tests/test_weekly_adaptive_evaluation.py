from pathlib import Path

from server.weekly_review_evaluation import load_cases, markdown_report, run_evaluation


CASES = Path("evaluation/weekly_adaptive/cases_v1.jsonl")


def test_public_case_set_is_unique_fictional_and_large_enough() -> None:
    cases = load_cases(CASES)
    assert len(cases) >= 30
    assert len({case.case_id for case in cases}) == len(cases)
    serialized = "\n".join(case.model_dump_json() for case in cases).lower()
    assert "@" not in serialized
    assert "token" not in serialized
    assert "api_key" not in serialized


def test_evaluation_is_deterministic_and_meets_safety_gates() -> None:
    cases = load_cases(CASES)
    first = run_evaluation(cases)
    second = run_evaluation(cases)
    assert first == second
    summary = first["summary"]
    assert summary["weekly_facts_accuracy"] == 1.0
    assert summary["rule_consistency"] == 1.0
    assert summary["warning_retention"] == 1.0
    assert summary["unauthorized_write_rate"] == 0.0
    assert summary["rejected_proposal_write_rate"] == 0.0
    assert summary["duplicate_apply_rate"] == 0.0
    assert summary["proposal_rule_violation_rate"] == 0.0
    assert summary["fallback_success_rate"] == 1.0


def test_markdown_report_is_safe_and_reproducible() -> None:
    text = markdown_report(run_evaluation(load_cases(CASES)))
    assert "python scripts/evaluate_weekly_adaptive.py" in text
    assert "Provider raw" not in text
    assert "API Key" not in text
