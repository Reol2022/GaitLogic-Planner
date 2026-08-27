from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from statistics import fmean, pstdev

from pydantic import ValidationError

from server.agent.competition_ablation.pipeline import (
    enforce_validator,
    prepare_ablation_input,
)
from server.agent.competition_ablation.provider import (
    AblationProvider,
    AblationProviderCallError,
    AblationSchemaError,
)
from server.agent.competition_ablation.scorer import score_ablation_output
from server.agent.competition_ablation.schemas import (
    AblationCategory,
    AblationVariant,
    CompetitionAblationCase,
    CompetitionAblationReport,
    CompetitionCaseRun,
    EfficiencyMetrics,
    MetricFraction,
    RunMetrics,
    VariantSummary,
)
from server.agent.competition_ablation.variants import (
    MAIN_VARIANTS,
    SAFETY_VARIANTS,
    variant_config,
)


_METRIC_NAMES = tuple(RunMetrics.model_fields)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _empty_metrics() -> RunMetrics:
    return RunMetrics(
        **{
            name: MetricFraction(numerator=0, denominator=0)
            for name in _METRIC_NAMES
        }
    )


def _empty_efficiency(*, tool_calls: int = 0, reflect_calls: int = 0) -> EfficiencyMetrics:
    return EfficiencyMetrics(
        provider_calls=1,
        tool_calls=tool_calls,
        reflect_calls=reflect_calls,
        latency_ms=0.0,
        provider_retry_count=0,
    )


def aggregate_variant(
    variant: AblationVariant,
    runs: list[CompetitionCaseRun],
) -> VariantSummary:
    selected = [item for item in runs if item.variant == variant]
    fractions: dict[str, MetricFraction] = {}
    means: dict[str, float] = {}
    for name in _METRIC_NAMES:
        numerator = sum(getattr(item.metrics, name).numerator for item in selected)
        denominator = sum(getattr(item.metrics, name).denominator for item in selected)
        fraction = MetricFraction(numerator=numerator, denominator=denominator)
        fractions[name] = fraction
        means[name] = fraction.value
    latencies = [item.efficiency.latency_ms for item in selected]
    tokens = [
        float(item.efficiency.total_tokens)
        for item in selected
        if item.efficiency.total_tokens is not None
    ]
    return VariantSummary(
        variant=variant,
        success_count=sum(item.status == "SUCCEEDED" for item in selected),
        failure_count=sum(item.status != "SUCCEEDED" for item in selected),
        metric_means=means,
        metric_fractions=fractions,
        average_latency_ms=fmean(latencies) if latencies else 0.0,
        latency_std_ms=pstdev(latencies) if len(latencies) > 1 else 0.0,
        average_total_tokens=fmean(tokens) if tokens else 0.0,
        token_std=pstdev(tokens) if len(tokens) > 1 else 0.0,
        provider_calls=sum(item.efficiency.provider_calls for item in selected),
        tool_calls=sum(item.efficiency.tool_calls for item in selected),
        reflect_calls=sum(item.efficiency.reflect_calls for item in selected),
    )


class CompetitionAblationRunner:
    def __init__(self, provider: AblationProvider) -> None:
        self.provider = provider

    def run_case(
        self,
        *,
        case: CompetitionAblationCase,
        variant: AblationVariant,
        run_index: int,
    ) -> CompetitionCaseRun:
        config = variant_config(variant)
        prepared = prepare_ablation_input(case, config)
        tool_calls = len(prepared.tool_names) + len(prepared.reflect_tool_names)
        try:
            provided = self.provider.generate(
                case=case,
                config=config,
                payload=prepared.payload,
                tool_calls=tool_calls,
                reflect_calls=len(prepared.reflect_tool_names),
            )
            output = provided.output
            validator_codes: list[str] = []
            if config.validator_enabled:
                output, validator_codes = enforce_validator(
                    case=case,
                    payload=prepared.payload,
                    output=output,
                )
            metrics, assertion_codes = score_ablation_output(
                case=case,
                prepared=prepared,
                output=output,
            )
            return CompetitionCaseRun(
                case_id=case.case_id,
                category=case.category,
                variant=variant,
                run_index=run_index,
                status="SUCCEEDED",
                metrics=metrics,
                efficiency=provided.efficiency,
                assertion_codes=list(dict.fromkeys([*validator_codes, *assertion_codes])),
            )
        except AblationSchemaError as exc:
            return CompetitionCaseRun(
                case_id=case.case_id,
                category=case.category,
                variant=variant,
                run_index=run_index,
                status="SCHEMA_FAILED",
                metrics=_empty_metrics(),
                efficiency=_empty_efficiency(
                    tool_calls=tool_calls,
                    reflect_calls=len(prepared.reflect_tool_names),
                ),
                safe_error_codes=["ABLATION_SCHEMA_FAILED", *exc.codes],
            )
        except ValidationError:
            return CompetitionCaseRun(
                case_id=case.case_id,
                category=case.category,
                variant=variant,
                run_index=run_index,
                status="SCHEMA_FAILED",
                metrics=_empty_metrics(),
                efficiency=_empty_efficiency(
                    tool_calls=tool_calls,
                    reflect_calls=len(prepared.reflect_tool_names),
                ),
                safe_error_codes=["ABLATION_SCHEMA_FAILED"],
            )
        except AblationProviderCallError as exc:
            return CompetitionCaseRun(
                case_id=case.case_id,
                category=case.category,
                variant=variant,
                run_index=run_index,
                status="PROVIDER_FAILED",
                metrics=_empty_metrics(),
                efficiency=_empty_efficiency(
                    tool_calls=tool_calls,
                    reflect_calls=len(prepared.reflect_tool_names),
                ),
                safe_error_codes=["ABLATION_PROVIDER_FAILED", exc.code],
            )
        except Exception:
            return CompetitionCaseRun(
                case_id=case.case_id,
                category=case.category,
                variant=variant,
                run_index=run_index,
                status="PROVIDER_FAILED",
                metrics=_empty_metrics(),
                efficiency=_empty_efficiency(
                    tool_calls=tool_calls,
                    reflect_calls=len(prepared.reflect_tool_names),
                ),
                safe_error_codes=["ABLATION_PROVIDER_FAILED"],
            )

    def run(
        self,
        *,
        cases: list[CompetitionAblationCase],
        phase: str,
        runs_per_case: int,
        fail_fast: bool = False,
        case_ids: set[str] | None = None,
        variants_override: tuple[AblationVariant, ...] | None = None,
        existing_runs: list[CompetitionCaseRun] | None = None,
    ) -> CompetitionAblationReport:
        if phase == "pilot":
            selected_cases = [item for item in cases if item.pilot]
            variants = MAIN_VARIANTS
        elif phase == "full":
            selected_cases = cases
            variants = MAIN_VARIANTS
        elif phase == "safety":
            selected_cases = [item for item in cases if item.safety_case]
            variants = SAFETY_VARIANTS
        else:
            raise ValueError(f"Unknown ablation phase: {phase}")
        if case_ids is not None:
            selected_cases = [item for item in selected_cases if item.case_id in case_ids]
        if variants_override is not None:
            variants = variants_override
        reusable = {
            (item.case_id, item.variant, item.run_index): item
            for item in (existing_runs or [])
            if item.status == "SUCCEEDED"
        }
        # Keep successful records that are outside an optional checkpoint subset.
        # This lets the real-provider supervisor persist a completed case/variant
        # without discarding earlier completed combinations after a transient
        # network failure. Failed records are deliberately not retained: they are
        # retried on the next invocation of that selected combination.
        runs_by_key: dict[tuple[str, AblationVariant, int], CompetitionCaseRun] = dict(
            reusable
        )
        stopped = False
        for case in selected_cases:
            for variant in variants:
                for run_index in range(1, runs_per_case + 1):
                    key = (case.case_id, variant, run_index)
                    result = reusable.get(key)
                    if result is None:
                        result = self.run_case(
                            case=case,
                            variant=variant,
                            run_index=run_index,
                        )
                    runs_by_key[key] = result
                    if fail_fast and result.status != "SUCCEEDED":
                        stopped = True
                        break
                if stopped:
                    break
            if stopped:
                break
        runs = list(runs_by_key.values())
        summary_variants = (
            MAIN_VARIANTS if phase in {"pilot", "full"} else SAFETY_VARIANTS
        )
        summaries = [
            aggregate_variant(variant, runs) for variant in summary_variants
        ]
        provider_mode = (
            "offline"
            if self.provider.provider_alias == "deterministic_offline"
            else "real"
        )
        return CompetitionAblationReport(
            phase=phase,
            generated_at=datetime.now(timezone.utc),
            git_commit=_git_commit(),
            provider_mode=provider_mode,
            provider_alias=self.provider.provider_alias,
            model_alias=self.provider.model_alias,
            thinking_mode=self.provider.thinking_mode,
            temperature=self.provider.temperature,
            max_output_tokens=self.provider.max_output_tokens,
            runs_per_case=runs_per_case,
            case_count=len({item.case_id for item in runs}),
            total_model_calls=len(runs),
            summaries=summaries,
            runs=runs,
            limitations=[
                "Fixed public fictional cases are not a longitudinal athlete study.",
                "Deterministic scoring covers bounded safety and factual contracts, not all language quality.",
                "Provider outputs are stochastic when the provider does not support a fixed seed.",
            ],
        )

    def close(self) -> None:
        self.provider.close()
