from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from planner_core.config import Settings, get_settings
from pydantic import ValidationError

from server.agent.competition_ablation.schemas import (
    AblationConfig,
    AblationDecision,
    AblationProviderOutput,
    CompetitionAblationCase,
    EfficiencyMetrics,
)
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.model_tasks import ModelTaskType, task_model_profile
from server.provider_reliability import (
    RetryPolicy,
    classify_provider_exception,
    provider_failure,
)


class AblationSchemaError(ValueError):
    def __init__(self, codes: list[str]) -> None:
        super().__init__("Provider output failed the ablation schema")
        self.codes = codes


class AblationProviderCallError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__("Ablation provider call failed")
        self.code = code


def safe_ablation_provider_error_code(exc: Exception) -> str:
    """Map a Provider exception to a stable code without retaining raw details."""

    if getattr(exc, "status_code", None) == 402:
        return "PROVIDER_PAYMENT_REQUIRED"
    return classify_provider_exception(exc).category.value


@dataclass(frozen=True)
class ProviderResult:
    output: AblationProviderOutput
    efficiency: EfficiencyMetrics


class AblationProvider(Protocol):
    provider_alias: str
    model_alias: str
    thinking_mode: str
    max_output_tokens: int
    temperature: float

    def generate(
        self,
        *,
        case: CompetitionAblationCase,
        config: AblationConfig,
        payload: dict[str, object],
        tool_calls: int,
        reflect_calls: int,
    ) -> ProviderResult: ...

    def close(self) -> None: ...


class DeterministicAblationProvider:
    """Framework-test provider; it never connects to a model or network."""

    provider_alias = "deterministic_offline"
    model_alias = "deterministic-ablation-v1"
    thinking_mode = "disabled"
    max_output_tokens = 1200
    temperature = 0.2

    def generate(
        self,
        *,
        case: CompetitionAblationCase,
        config: AblationConfig,
        payload: dict[str, object],
        tool_calls: int,
        reflect_calls: int,
    ) -> ProviderResult:
        started = perf_counter()
        visible_facts = payload.get("facts") if isinstance(payload.get("facts"), dict) else {}
        assertions = {
            item.fact_id: visible_facts.get(item.fact_id)
            for item in case.expected_fact_assertions
            if item.fact_id in visible_facts
        }
        readiness = payload.get("decision_readiness") or {}
        decisions: list[AblationDecision] = []
        conflict_domains = {
            str(item.get("domain"))
            for item in case.evidence_relations
            if item.get("type") == "conflict"
        }
        for expected in case.expected_decision_domains:
            exposed = readiness.get(expected.domain) if isinstance(readiness, dict) else None
            blocked = exposed == "BLOCKED"
            if expected.expected_decision and not blocked:
                decisions.append(
                    AblationDecision(
                        domain=expected.domain,
                        decision=expected.expected_decision,
                        support_ids=[item.fact_id for item in case.expected_fact_assertions[:2]],
                        certainty=(
                            "SUPPORTED"
                            if config.evidence_judge_enabled
                            or expected.domain not in conflict_domains
                            else "ABSOLUTE"
                        ),
                    )
                )
        has_usable = any(
            item.readiness in {"READY", "PARTIAL"}
            for item in case.expected_decision_domains
        )
        # Earlier architectures reproduce the historical false-global-block
        # behavior only in the deterministic framework fixture.
        global_blocked = (
            case.category.value == "PARTIAL_FACTS"
            and has_usable
            and not config.decision_readiness_enabled
        )
        conflicts = [
            str(item.get("id"))
            for item in payload.get("evidence_relations", [])
            if isinstance(item, dict) and item.get("type") == "conflict"
        ]
        if not config.evidence_judge_enabled:
            conflicts = []
        proposal_status = case.proposal_expected_status
        if case.task_type == "PROPOSAL" and not config.validator_enabled:
            proposal_status = "READY"
        output = AblationProviderOutput(
            completed=not global_blocked,
            global_blocked=global_blocked,
            answer="Deterministic public fictional ablation output.",
            fact_assertions=assertions,
            decisions=[] if global_blocked else decisions,
            warning_codes=list(case.expected_required_warnings),
            limitation_codes=(
                ["PARTIAL_FACTS_PRESENT"]
                if case.expected_readiness.value == "PARTIAL"
                else []
            ),
            detected_conflicts=conflicts,
            proposal_status=proposal_status,
        )
        return ProviderResult(
            output=output,
            efficiency=EfficiencyMetrics(
                provider_calls=1,
                tool_calls=tool_calls,
                reflect_calls=reflect_calls,
                prompt_tokens=100,
                reasoning_tokens=0,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=(perf_counter() - started) * 1000,
                provider_retry_count=0,
            ),
        )

    def close(self) -> None:
        return None


class RealAblationProvider:
    """Real-provider adapter used only by the explicit competition CLI."""

    temperature = 0.2

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.coach_agent_enabled:
            raise RuntimeError("Coach provider is disabled")
        if not all(
            (
                self.settings.coach_agent_provider,
                self.settings.coach_agent_api_key,
                self.settings.coach_agent_base_url,
                self.settings.coach_agent_model,
            )
        ):
            raise RuntimeError("Coach provider configuration is incomplete")
        self.gateway = OpenAICompatibleAgentGateway(self.settings)
        profile = task_model_profile(self.settings, ModelTaskType.COACH_ANALYSIS)
        self.provider_alias = self.settings.coach_agent_provider
        self.model_alias = profile.model
        self.thinking_mode = "enabled" if profile.thinking_enabled else "disabled"
        self.max_output_tokens = profile.max_output_tokens

    @staticmethod
    def _system_instructions(config: AblationConfig) -> str:
        enabled = [
            name
            for name, active in {
                "tools": config.tools_enabled,
                "rules": config.rules_enabled,
                "rag": config.rag_enabled,
                "decision_readiness": config.decision_readiness_enabled,
                "evidence_judge": config.evidence_judge_enabled,
                "reflect": config.reflect_enabled,
                "validator": config.validator_enabled,
            }.items()
            if active
        ]
        return (
            "You are running an offline public-fictional training decision ablation. "
            "Use only the supplied payload. Do not claim medical diagnosis, plan mutation, "
            "or sources that are not supplied. Architecture modules enabled: "
            + ", ".join(enabled)
            + ". Return one JSON object matching the requested schema."
        )

    def generate(
        self,
        *,
        case: CompetitionAblationCase,
        config: AblationConfig,
        payload: dict[str, object],
        tool_calls: int,
        reflect_calls: int,
    ) -> ProviderResult:
        started = perf_counter()
        request = {
            "task": case.task_type,
            "query": case.user_query,
            "input": payload,
            "output_contract": {
                "completed": "boolean",
                "global_blocked": "boolean",
                "answer": "string",
                "fact_assertions": "object keyed only by supplied fact IDs",
                "decisions": [
                    {
                        "domain": "lowercase snake_case string from decision_readiness",
                        "decision": "UPPER_SNAKE_CASE code, at most 120 characters",
                        "support_ids": ["supplied fact or evidence IDs"],
                        "certainty": "LIMITED|SUPPORTED|ABSOLUTE",
                    }
                ],
                "warning_codes": ["string"],
                "limitation_codes": ["string"],
                "detected_conflicts": ["supplied conflict ID"],
                "proposal_status": "READY|BLOCKED|NOT_APPLICABLE",
            },
        }
        request["output_requirements"] = [
            "Return every top-level field exactly once.",
            "Use empty arrays and an empty object when no values exist.",
            "Do not add fields outside this contract.",
            "support_ids may contain only IDs visible in the input payload.",
        ]
        messages = [
            {"role": "system", "content": self._system_instructions(config)},
            {
                "role": "user",
                "content": json.dumps(
                    request,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ]
        policy = RetryPolicy(
            max_retries=self.settings.coach_agent_max_retries,
            initial_backoff_seconds=self.settings.coach_agent_retry_initial_backoff_seconds,
            max_backoff_seconds=self.settings.coach_agent_retry_max_backoff_seconds,
        )
        response = None
        retry_count = 0
        for attempt in range(policy.max_attempts):
            try:
                response = self.gateway.client.chat.completions.create(
                    model=self.model_alias,
                    messages=messages,
                    response_format={"type": "json_object"},
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                    extra_body={"thinking": {"type": self.thinking_mode}},
                )
                retry_count = attempt
                break
            except Exception as exc:
                failure = classify_provider_exception(exc)
                if policy.can_retry(
                    attempt=attempt,
                    failure=provider_failure(failure.category),
                ):
                    policy.wait(attempt=attempt)
                    continue
                raise AblationProviderCallError(
                    safe_ablation_provider_error_code(exc)
                ) from exc
        if response is None:
            raise AblationProviderCallError("PROVIDER_NO_RESPONSE")
        if not getattr(response, "choices", None):
            raise RuntimeError("Provider returned no choices")
        content = getattr(response.choices[0].message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Provider returned empty structured content")
        try:
            output = AblationProviderOutput.model_validate_json(content)
        except ValidationError as exc:
            codes = []
            for error in exc.errors(include_input=False, include_url=False):
                location = "_".join(str(item).upper() for item in error["loc"][:2])
                error_type = str(error["type"]).upper().replace(".", "_")
                codes.append(f"SCHEMA_{location}_{error_type}"[:120])
            raise AblationSchemaError(list(dict.fromkeys(codes))) from exc
        except ValueError as exc:
            raise AblationSchemaError(["SCHEMA_INVALID_JSON"]) from exc
        usage = getattr(response, "usage", None)
        details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(details, "reasoning_tokens", None)
        return ProviderResult(
            output=output,
            efficiency=EfficiencyMetrics(
                provider_calls=1,
                tool_calls=tool_calls,
                reflect_calls=reflect_calls,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                reasoning_tokens=reasoning_tokens,
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                latency_ms=(perf_counter() - started) * 1000,
                provider_retry_count=retry_count,
            ),
        )

    def close(self) -> None:
        self.gateway.close()
