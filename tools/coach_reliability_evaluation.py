"""Run resumable, deidentified local Coach provider evaluations.

Examples (run from the repository root):

  python tools/coach_reliability_evaluation.py --env-file ..\\Gaitlogic-planner\\.env \\
      --profile flash --repeats 2 --execute
  python tools/coach_reliability_evaluation.py --report var/evaluations/coach-reliability/report.json

The JSONL checkpoint only contains case/profile IDs, stage statuses, aggregate
quality flags, timing, token counts, and optional configured cost.  It never
stores prompts, answers, tool payloads, raw provider errors, or reasoning.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import Settings
from server.agent.evaluation.fixtures import EVALUATION_FIXTURES, build_evaluation_registry
from server.agent.evaluation.reliability_suite import CoachReliabilityCase, coach_reliability_cases
from server.agent.enums import AgentRunStatus, AgentTraceEventType, AgentTraceStatus
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.agent.reliability import provider_failure_category
from server.agent.schemas import AgentRequest
from server.agent.training_context_builder import AgentTrainingContextBuilder


DEFAULT_OUTPUT = ROOT / "var" / "evaluations" / "coach-reliability" / "runs.jsonl"


@dataclass(frozen=True)
class EvaluationProfile:
    name: str
    model: str
    thinking_enabled: bool


@dataclass(frozen=True)
class SafeEvaluationRecord:
    case_id: str
    profile: str
    model: str
    thinking_enabled: bool
    repeat: int
    completed_at: str
    final_status: str
    provider_status: str
    parser_passed: bool
    validator_passed: bool
    failure_category: str | None
    context_fact_count: int
    facts_loaded: bool
    limitations_retained: bool | None
    no_plan_write_claim: bool
    answer_present: bool
    duration_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    estimated_cost_usd: float | None
    provider_retried: bool = False
    transient_provider_failure_category: str | None = None
    provider_response_received: bool = False


def _profiles(settings: Settings) -> dict[str, EvaluationProfile]:
    flash = settings.coach_agent_model or "deepseek-flash"
    pro = settings.plan_design_model or "deepseek-v4-pro"
    return {
        "flash": EvaluationProfile("flash", flash, False),
        "flash-thinking": EvaluationProfile("flash-thinking", flash, True),
        "pro-thinking": EvaluationProfile("pro-thinking", pro, True),
    }


def _settings_for_profile(settings: Settings, profile: EvaluationProfile) -> Settings:
    return settings.model_copy(
        update={
            "coach_chat_fast_model": profile.model,
            "coach_fact_query_model": profile.model,
            "coach_analysis_model": profile.model,
            "plan_design_model": profile.model,
            "coach_agent_thinking_mode": "enabled" if profile.thinking_enabled else "disabled",
        }
    )


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, timeout=5
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _read_records(path: Path) -> dict[tuple[str, str, int], SafeEvaluationRecord]:
    if not path.exists():
        return {}
    records: dict[tuple[str, str, int], SafeEvaluationRecord] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        record = SafeEvaluationRecord(**payload)
        records[(record.case_id, record.profile, record.repeat)] = record
    return records


def _append_record(path: Path, record: SafeEvaluationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=True, separators=(",", ":")) + "\n")


def _quantile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((len(values) - 1) * percentile)))
    return round(values[index], 3)


def summarize(records: list[SafeEvaluationRecord]) -> dict[str, Any]:
    by_profile: dict[str, list[SafeEvaluationRecord]] = {}
    for record in records:
        by_profile.setdefault(record.profile, []).append(record)
    result: dict[str, Any] = {"git_commit": _git_commit(), "profiles": {}}
    for profile, items in sorted(by_profile.items()):
        durations = [item.duration_ms for item in items]
        prompt_tokens = sum(item.prompt_tokens or 0 for item in items)
        completion_tokens = sum(item.completion_tokens or 0 for item in items)
        cost_values = [item.estimated_cost_usd for item in items if item.estimated_cost_usd is not None]
        result["profiles"][profile] = {
            "runs": len(items),
            "succeeded": sum(item.final_status == AgentRunStatus.SUCCEEDED.value for item in items),
            "provider_succeeded": sum(item.provider_status == "SUCCEEDED" for item in items),
            "provider_response_received": sum(item.provider_response_received for item in items),
            "parser_passed": sum(item.parser_passed for item in items),
            "validator_passed": sum(item.validator_passed for item in items),
            "facts_loaded": sum(item.facts_loaded for item in items),
            "no_plan_write_claim": sum(item.no_plan_write_claim for item in items),
            "duration_p50_ms": _quantile(durations, 0.5),
            "duration_p95_ms": _quantile(durations, 0.95),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": round(sum(cost_values), 8) if cost_values else None,
            "provider_retried": sum(item.provider_retried for item in items),
            "failure_categories": {
                category: sum(
                    item.failure_category == category
                    and item.final_status != AgentRunStatus.SUCCEEDED.value
                    for item in items
                )
                for category in sorted(
                    {
                        item.failure_category
                        for item in items
                        if item.failure_category
                        and item.final_status != AgentRunStatus.SUCCEEDED.value
                    }
                )
            },
            "transient_provider_failure_categories": {
                category: sum(item.transient_provider_failure_category == category for item in items)
                for category in sorted(
                    {item.transient_provider_failure_category for item in items if item.transient_provider_failure_category}
                )
            },
        }
    return result


def _cost(
    pricing: dict[str, Any], model: str, prompt_tokens: int | None, completion_tokens: int | None
) -> float | None:
    rates = pricing.get(model)
    if not isinstance(rates, dict) or prompt_tokens is None or completion_tokens is None:
        return None
    try:
        return round(
            prompt_tokens / 1_000_000 * float(rates["input_per_million_usd"])
            + completion_tokens / 1_000_000 * float(rates["output_per_million_usd"]),
            8,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _failure_category(
    agent: GaitLogicCoachAgent,
    gateway: OpenAICompatibleAgentGateway,
    *,
    final_status: str,
) -> str | None:
    if final_status == AgentRunStatus.SUCCEEDED.value:
        return None
    reliability = gateway.last_reliability
    if reliability.failure_category is not None:
        return provider_failure_category(reliability.failure_category).value
    trace = agent.last_trace
    if trace is None:
        return None
    for event in reversed(trace.events):
        if event.failure_category:
            return event.failure_category
    return None


def _transient_provider_failure_category(agent: GaitLogicCoachAgent) -> str | None:
    trace = agent.last_trace
    if trace is None:
        return None
    for event in reversed(trace.events):
        if (
            event.event_type == AgentTraceEventType.PROVIDER_CALL_FAILED
            and event.retried
            and event.failure_category
        ):
            return event.failure_category
    return None


def _run_case(
    *,
    case: CoachReliabilityCase,
    settings: Settings,
    profile: EvaluationProfile,
    repeat: int,
    pricing: dict[str, Any],
) -> SafeEvaluationRecord:
    fixture = EVALUATION_FIXTURES[case.fixture_name]
    registry = build_evaluation_registry(fixture)
    gateway = OpenAICompatibleAgentGateway(settings)
    agent = GaitLogicCoachAgent(
        gateway=gateway,
        registry=registry,
        context_builder=AgentTrainingContextBuilder(registry=registry),
    )
    started = perf_counter()
    response = None
    try:
        response = agent.run(
            AgentRequest.for_authenticated_user(
                user_id=900001,
                message=case.prompt,
                intent=case.intent,
            )
        )
    except Exception:
        # The checkpoint must survive an unexpected local evaluation failure,
        # but no exception details are retained because they may contain
        # provider or environment data.
        response = None
    finally:
        gateway.close()
    duration_ms = round((perf_counter() - started) * 1000, 3)
    trace = agent.last_trace
    successful_provider_events = [
        event
        for event in (trace.events if trace else [])
        if event.event_type == AgentTraceEventType.PROVIDER_CALL_COMPLETED
        and event.status == AgentTraceStatus.SUCCEEDED
    ]
    prompt_tokens = sum(event.prompt_tokens or 0 for event in successful_provider_events) or None
    completion_tokens = sum(event.completion_tokens or 0 for event in successful_provider_events) or None
    validator_passed = any(
        event.event_type == AgentTraceEventType.RESPONSE_VALIDATED
        and event.status == AgentTraceStatus.SUCCEEDED
        for event in (trace.events if trace else [])
    )
    context = agent.last_context
    context_fact_count = len(context.tool_results) if context else 0
    answer = response.answer if response is not None and response.answer else ""
    plan_write_markers = ("applied your official training plan", "updated your official training plan")
    no_plan_write_claim = not any(marker in answer.lower() for marker in plan_write_markers)
    return SafeEvaluationRecord(
        case_id=case.case_id,
        profile=profile.name,
        model=profile.model,
        thinking_enabled=profile.thinking_enabled,
        repeat=repeat,
        completed_at=datetime.now(timezone.utc).isoformat(),
        final_status=(response.status.value if response is not None else AgentRunStatus.MODEL_FAILED.value),
        provider_status=gateway.last_usage.status,
        parser_passed=bool(successful_provider_events),
        validator_passed=validator_passed,
        failure_category=_failure_category(
            agent,
            gateway,
            final_status=(response.status.value if response is not None else AgentRunStatus.MODEL_FAILED.value),
        ),
        context_fact_count=context_fact_count,
        facts_loaded=context_fact_count >= case.minimum_context_facts,
        limitations_retained=(
            bool(response.limitations) if case.requires_limitation and response is not None else None
        ),
        no_plan_write_claim=no_plan_write_claim,
        answer_present=bool(answer.strip()),
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=_cost(pricing, profile.model, prompt_tokens, completion_tokens),
        provider_retried=any(
            event.event_type == AgentTraceEventType.PROVIDER_CALL_FAILED and event.retried
            for event in (trace.events if trace else [])
        ),
        transient_provider_failure_category=_transient_provider_failure_category(agent),
        provider_response_received=bool(
            gateway.last_response_metadata.get("provider_response_received", False)
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Local, untracked settings file used only with --execute.")
    parser.add_argument("--profile", choices=("flash", "flash-thinking", "pro-thinking"), action="append")
    parser.add_argument("--case", dest="case_ids", action="append", help="Run one fixed case ID; repeatable.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pricing-json", type=Path, help="Optional local model pricing JSON; never committed.")
    parser.add_argument("--report", type=Path, help="Write an aggregate JSON report from existing checkpoints.")
    parser.add_argument("--execute", action="store_true", help="Permit real provider calls using only fictional fixtures.")
    parser.add_argument("--rerun-failed", action="store_true", help="Re-run checkpoint records whose final status was not SUCCEEDED.")
    parser.add_argument("--max-runs", type=int, default=0, help="Bound one invocation for recoverable long runs; 0 means all pending.")
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        help="Optional bounded per-request timeout for this local run; records a safe timeout outcome.",
    )
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.request_timeout_seconds is not None and args.request_timeout_seconds <= 0:
        parser.error("--request-timeout-seconds must be positive")
    records = _read_records(args.output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summarize(list(records.values())), indent=2), encoding="utf-8")
    if not args.execute:
        print(json.dumps({"pending_records": len(records), "execute": False}, ensure_ascii=True))
        return 0
    if args.env_file is None:
        parser.error("--env-file is required with --execute")
    settings = Settings(_env_file=args.env_file)
    pricing = json.loads(args.pricing_json.read_text(encoding="utf-8")) if args.pricing_json else {}
    profiles = _profiles(settings)
    selected = args.profile or ["flash", "pro-thinking"]
    cases = coach_reliability_cases()
    if args.case_ids:
        selected_ids = set(args.case_ids)
        cases = tuple(case for case in cases if case.case_id in selected_ids)
        unknown_ids = selected_ids - {case.case_id for case in cases}
        if unknown_ids:
            parser.error(f"unknown --case value(s): {', '.join(sorted(unknown_ids))}")
    completed = 0
    for profile_name in selected:
        profile = profiles[profile_name]
        profile_settings = _settings_for_profile(settings, profile)
        if args.request_timeout_seconds is not None:
            profile_settings = profile_settings.model_copy(
                update={
                    "coach_agent_total_timeout_seconds": args.request_timeout_seconds,
                    "coach_agent_read_timeout_seconds": args.request_timeout_seconds,
                }
            )
        for case in cases:
            for repeat in range(1, args.repeats + 1):
                key = (case.case_id, profile.name, repeat)
                if key in records and (
                    not args.rerun_failed
                    or records[key].final_status == AgentRunStatus.SUCCEEDED.value
                ):
                    continue
                record = _run_case(
                    case=case,
                    settings=profile_settings,
                    profile=profile,
                    repeat=repeat,
                    pricing=pricing,
                )
                _append_record(args.output, record)
                records[key] = record
                completed += 1
                if args.max_runs and completed >= args.max_runs:
                    break
            if args.max_runs and completed >= args.max_runs:
                break
        if args.max_runs and completed >= args.max_runs:
            break
    if args.report:
        args.report.write_text(json.dumps(summarize(list(records.values())), indent=2), encoding="utf-8")
    print(json.dumps({"completed": completed, "checkpoint_records": len(records)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
