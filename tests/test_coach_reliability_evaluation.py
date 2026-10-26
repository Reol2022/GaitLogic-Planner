from __future__ import annotations

from dataclasses import asdict, replace

from server.agent.evaluation.reliability_suite import coach_reliability_cases
from planner_core.config import Settings
from tools.coach_reliability_evaluation import (
    EvaluationProfile,
    SafeEvaluationRecord,
    _settings_for_profile,
    summarize,
)


def _record(*, profile: str = "flash", duration_ms: float = 100.0) -> SafeEvaluationRecord:
    return SafeEvaluationRecord(
        case_id="daily_plan_fact",
        profile=profile,
        model="fictional-model",
        thinking_enabled=False,
        repeat=1,
        completed_at="2026-10-26T00:00:00+00:00",
        final_status="SUCCEEDED",
        provider_status="SUCCEEDED",
        parser_passed=True,
        validator_passed=True,
        failure_category=None,
        context_fact_count=1,
        facts_loaded=True,
        limitations_retained=None,
        no_plan_write_claim=True,
        answer_present=True,
        duration_ms=duration_ms,
        prompt_tokens=100,
        completion_tokens=20,
        estimated_cost_usd=None,
    )


def test_reliability_case_set_covers_the_reviewed_task_boundaries() -> None:
    cases = coach_reliability_cases()
    assert len(cases) == 8
    assert {case.case_id for case in cases} == {
        "daily_plan_fact",
        "recent_load_status",
        "quality_session_analysis",
        "two_week_race_analysis",
        "next_week_adjustment_analysis",
        "missing_data_boundary",
        "conflicted_or_unknown_facts",
        "no_unnecessary_plan_change",
    }
    assert all(case.must_not_apply_plan for case in cases)
    assert all("fictional" in case.prompt.lower() for case in cases)


def test_checkpoint_record_contains_only_aggregate_safe_fields() -> None:
    payload = asdict(_record())
    forbidden_keys = {"raw_prompt", "answer", "reasoning", "tool_result", "trace_id", "user_id"}
    assert forbidden_keys.isdisjoint(payload)


def test_summary_reports_counts_and_latency_without_claiming_missing_costs() -> None:
    summary = summarize([_record(duration_ms=100.0), _record(duration_ms=500.0)])
    flash = summary["profiles"]["flash"]
    assert flash["runs"] == 2
    assert flash["succeeded"] == 2
    assert flash["provider_response_received"] == 0
    assert flash["duration_p50_ms"] == 100.0
    assert flash["duration_p95_ms"] == 500.0
    assert flash["estimated_cost_usd"] is None


def test_successful_retry_is_not_counted_as_a_terminal_failure() -> None:
    successful_retry = replace(
        _record(),
        failure_category="PROVIDER_TIMEOUT",
        provider_retried=True,
        transient_provider_failure_category="PROVIDER_TIMEOUT",
    )
    summary = summarize(
        [
            successful_retry,
            replace(
                successful_retry,
                final_status="MODEL_FAILED",
                provider_retried=False,
                transient_provider_failure_category=None,
            )
        ]
    )
    flash = summary["profiles"]["flash"]
    assert flash["failure_categories"] == {"PROVIDER_TIMEOUT": 1}
    assert flash["provider_retried"] == 1
    assert flash["transient_provider_failure_categories"] == {"PROVIDER_TIMEOUT": 1}


def test_profile_override_preserves_the_existing_provider_credentials() -> None:
    base = Settings(
        _env_file=None,
        COACH_AGENT_ENABLED=True,
        COACH_AGENT_API_KEY="fictional-key",
        COACH_AGENT_BASE_URL="https://api.example.test/v1",
    )

    derived = _settings_for_profile(base, EvaluationProfile("flash", "fictional-flash", False))

    assert derived.coach_agent_enabled is True
    assert derived.coach_agent_api_key == "fictional-key"
    assert derived.coach_analysis_model == "fictional-flash"
    assert derived.coach_agent_thinking_mode == "disabled"
