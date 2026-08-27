from __future__ import annotations

import json
from pathlib import Path

import pytest

from planner_core.config import Settings
from server.agent.competition_ablation.loader import load_ablation_cases
from server.agent.competition_ablation.pipeline import (
    enforce_validator,
    prepare_ablation_input,
)
from server.agent.competition_ablation.provider import (
    AblationProviderCallError,
    DeterministicAblationProvider,
    safe_ablation_provider_error_code,
)
from server.agent.competition_ablation.runner import CompetitionAblationRunner
from server.agent.competition_ablation.schemas import (
    AblationProviderOutput,
    AblationVariant,
    CompetitionAblationCase,
)
from server.agent.competition_ablation.variants import MAIN_VARIANTS, variant_config


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation/competition_ablation/cases_v1.jsonl"


def _cases() -> list[CompetitionAblationCase]:
    return load_ablation_cases(CASES)


def _case(case_id: str) -> CompetitionAblationCase:
    return next(item for item in _cases() if item.case_id == case_id)


def test_case_set_is_balanced_public_fictional_data() -> None:
    cases = _cases()
    assert len(cases) == 24
    assert len({item.case_id for item in cases}) == 24
    assert {item.category.value for item in cases} == {
        "FACT_QUERY",
        "TRAINING_DECISION",
        "PARTIAL_FACTS",
        "EVIDENCE_CONFLICT",
        "REFLECT",
        "UNRESOLVABLE_EVIDENCE",
        "WEEKLY_REVIEW",
        "PROPOSAL_SAFETY",
    }
    serialized = CASES.read_text(encoding="utf-8").lower()
    for forbidden in ("email", "api_key", "database_url", "garmin_token", "user_id"):
        assert forbidden not in serialized


def test_loader_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    first = CASES.read_text(encoding="utf-8").splitlines()[0]
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text("\n".join([first] * 24), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_ablation_cases(duplicate)


def test_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    values = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
    values[0]["production_override"] = True
    target = tmp_path / "invalid.jsonl"
    target.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in values),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid ablation case"):
        load_ablation_cases(target)


def test_variant_configs_are_isolated_and_incremental() -> None:
    assert len(MAIN_VARIANTS) == 6
    assert not variant_config(AblationVariant.A_LLM_ONLY).tools_enabled
    assert variant_config(AblationVariant.B_TOOLS_LLM).tools_enabled
    assert variant_config(AblationVariant.C_TRUSTED_CORE).validator_enabled
    assert variant_config(AblationVariant.D_PARTIAL_FACTS).decision_readiness_enabled
    assert variant_config(AblationVariant.E_EVIDENCE_JUDGE).evidence_judge_enabled
    assert variant_config(AblationVariant.F_FULL_GAITLOGIC).reflect_enabled
    assert not variant_config(AblationVariant.G_FULL_WITHOUT_VALIDATOR).validator_enabled


def test_ablation_config_is_not_a_production_setting() -> None:
    fields = Settings.model_fields
    assert "ablation_config" not in fields
    assert not any(name.startswith("ablation_") for name in fields)


def test_tools_are_present_only_for_tool_variants() -> None:
    case = _case("fact_today_plan")
    baseline = prepare_ablation_input(case, variant_config(AblationVariant.A_LLM_ONLY))
    tools = prepare_ablation_input(case, variant_config(AblationVariant.B_TOOLS_LLM))
    assert baseline.tool_names == []
    assert tools.tool_names == ["get_today_workout"]
    assert "canonical_tool_results" not in baseline.payload
    assert "canonical_tool_results" in tools.payload


def test_decision_readiness_prevents_false_global_block() -> None:
    case = _case("partial_rpe_missing")
    runner = CompetitionAblationRunner(DeterministicAblationProvider())
    core = runner.run_case(
        case=case,
        variant=AblationVariant.C_TRUSTED_CORE,
        run_index=1,
    )
    partial = runner.run_case(
        case=case,
        variant=AblationVariant.D_PARTIAL_FACTS,
        run_index=1,
    )
    assert core.metrics.false_global_block.numerator == 1
    assert partial.metrics.false_global_block.numerator == 0
    assert partial.metrics.partial_facts_response.numerator == 1


def test_evidence_judge_detects_conflict_and_limits_overclaim() -> None:
    case = _case("conflict_recovery_signals")
    runner = CompetitionAblationRunner(DeterministicAblationProvider())
    without_judge = runner.run_case(
        case=case,
        variant=AblationVariant.D_PARTIAL_FACTS,
        run_index=1,
    )
    with_judge = runner.run_case(
        case=case,
        variant=AblationVariant.E_EVIDENCE_JUDGE,
        run_index=1,
    )
    assert without_judge.metrics.conflict_detection.numerator == 0
    assert with_judge.metrics.conflict_detection.numerator == 1
    assert with_judge.metrics.conflict_overclaim.numerator == 0


def test_reflect_resolves_only_supported_missing_evidence() -> None:
    resolvable = _case("reflect_recovery_resolved")
    unavailable = _case("missing_subjective_rpe")
    full = variant_config(AblationVariant.F_FULL_GAITLOGIC)
    prepared = prepare_ablation_input(resolvable, full)
    blocked = prepare_ablation_input(unavailable, full)
    assert prepared.reflect_tool_names == ["get_runner_state"]
    assert prepared.reflect_resolved_domains == ["recovery"]
    assert prepared.payload["facts"]["recovery_signal"] == "NORMAL"
    assert blocked.reflect_tool_names == []
    assert blocked.reflect_resolved_domains == []


def test_reflect_does_not_repeat_an_initial_tool() -> None:
    case = _case("reflect_no_gain")
    prepared = prepare_ablation_input(
        case,
        variant_config(AblationVariant.F_FULL_GAITLOGIC),
    )
    assert prepared.reflect_tool_names == []
    assert len(prepared.tool_names) == len(set(prepared.tool_names))


def test_validator_blocks_proposal_apply_but_unvalidated_variant_exposes_it() -> None:
    case = _case("proposal_increase_volume_blocked")
    raw = AblationProviderOutput(
        completed=True,
        global_blocked=False,
        answer="I updated your official training plan.",
        proposal_status="READY",
    )
    prepared = prepare_ablation_input(
        case,
        variant_config(AblationVariant.F_FULL_GAITLOGIC),
    )
    safe, codes = enforce_validator(case=case, payload=prepared.payload, output=raw)
    assert safe.proposal_status == "BLOCKED"
    assert not safe.completed
    assert "UNAUTHORIZED_PROPOSAL_REJECTED" in codes
    assert "UNSUPPORTED_OUTPUT_REJECTED" in codes


def test_safety_ablation_changes_only_validator_switch() -> None:
    full = variant_config(AblationVariant.F_FULL_GAITLOGIC)
    unsafe = variant_config(AblationVariant.G_FULL_WITHOUT_VALIDATOR)
    full_values = full.model_dump(exclude={"variant", "validator_enabled"})
    unsafe_values = unsafe.model_dump(exclude={"variant", "validator_enabled"})
    assert full_values == unsafe_values
    assert full.validator_enabled
    assert not unsafe.validator_enabled


def test_offline_pilot_is_repeatable_and_safe() -> None:
    first = CompetitionAblationRunner(DeterministicAblationProvider()).run(
        cases=_cases(),
        phase="pilot",
        runs_per_case=1,
    )
    second = CompetitionAblationRunner(DeterministicAblationProvider()).run(
        cases=_cases(),
        phase="pilot",
        runs_per_case=1,
    )
    assert first.case_count == 10
    assert first.total_model_calls == 60
    assert [item.metric_means for item in first.summaries] == [
        item.metric_means for item in second.summaries
    ]
    serialized = first.model_dump_json().lower()
    assert "user_query" not in serialized
    assert "reasoning_content" not in serialized
    assert "api_key" not in serialized
    assert "provider raw" not in serialized


def test_run_results_do_not_store_prompt_context_or_answer() -> None:
    fields = set(
        CompetitionAblationRunner(DeterministicAblationProvider())
        .run(cases=_cases(), phase="pilot", runs_per_case=1)
        .runs[0]
        .model_dump()
    )
    assert fields.isdisjoint(
        {"prompt", "context", "answer", "user_query", "reasoning_content", "raw_response"}
    )


def test_payment_required_uses_a_safe_terminal_code() -> None:
    class PaymentRequired(Exception):
        status_code = 402

    assert safe_ablation_provider_error_code(PaymentRequired()) == (
        "PROVIDER_PAYMENT_REQUIRED"
    )


def test_fail_fast_stops_the_entire_variant_matrix() -> None:
    class FailingProvider(DeterministicAblationProvider):
        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AblationProviderCallError("PROVIDER_PAYMENT_REQUIRED")

    report = CompetitionAblationRunner(FailingProvider()).run(
        cases=[_case("fact_today_plan")],
        phase="full",
        runs_per_case=3,
        fail_fast=True,
    )
    assert report.total_model_calls == 1
    assert report.runs[0].safe_error_codes[-1] == "PROVIDER_PAYMENT_REQUIRED"


def test_resume_reuses_successful_run_without_calling_provider() -> None:
    case = _case("fact_today_plan")
    existing = CompetitionAblationRunner(DeterministicAblationProvider()).run_case(
        case=case,
        variant=AblationVariant.A_LLM_ONLY,
        run_index=1,
    )

    class UnexpectedProvider(DeterministicAblationProvider):
        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("a successful resumed run must not call the Provider")

    report = CompetitionAblationRunner(UnexpectedProvider()).run(
        cases=[case],
        phase="full",
        runs_per_case=1,
        variants_override=(AblationVariant.A_LLM_ONLY,),
        existing_runs=[existing],
    )
    assert report.total_model_calls == 1
    assert report.runs[0] == existing
