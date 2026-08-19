from __future__ import annotations

import json
import copy
import logging
import re
from collections.abc import Callable
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from planner_core.config import Settings
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentTraceEventType, AgentTraceStatus
from server.agent.errors import AgentErrorCode
from server.agent.gateway import AgentExecutionState, AgentLLMGateway
from server.model_tasks import ModelTaskType, task_model_profile
from server.agent.knowledge_references import build_knowledge_reference_catalog
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.schemas import (
    AgentProviderUsage,
    ProviderAgentModelOutput,
    ProviderTodayModelOutput,
)
from server.agent.providers.security import validate_provider_base_url
from server.agent.schemas import (
    AgentContext,
    AgentModelOutput,
    AgentToolDefinition,
    AgentToolInvocation,
)
from server.agent.trace import AgentTrace
from server.agent.today_recommendation import (
    build_evidence_catalog,
    build_authoritative_today_facts,
    materialize_evidence_references,
)
from server.provider_reliability import (
    ProviderCallReliability,
    ProviderFailureCategory,
    RetryPolicy,
    classify_provider_exception,
    provider_failure,
)

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def redact_provider_text(value: str) -> str:
    return _PHONE.sub("[REDACTED_PHONE]", _EMAIL.sub("[REDACTED_EMAIL]", value))


def _redact_tree(value: Any) -> Any:
    if isinstance(value, str):
        return redact_provider_text(value)
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_tree(item) for key, item in value.items()}
    return value


def provider_context_payload(context: AgentContext) -> dict[str, Any]:
    """Create the only Context representation allowed to leave Agent Core."""
    payload = context.model_dump(
        mode="json",
        exclude={"user_id", "request_id", "tool_results"},
    )
    payload["tool_results"] = [
        {
            "tool_name": item.tool_name,
            "status": item.status.value,
            "data": item.data,
            "safe_error_code": item.safe_error_code.value if item.safe_error_code else None,
            "warnings": [warning.model_dump(mode="json") for warning in item.warnings],
        }
        for item in context.tool_results
    ]
    payload["available_evidence"] = (
        [
            {"id": item.id, "text": item.text}
            for item in build_evidence_catalog(context)
        ]
        if context.intent == AgentIntent.TODAY_RECOMMENDATION
        else []
    )
    knowledge_catalog = build_knowledge_reference_catalog(context)
    payload["available_knowledge_references"] = [
        {
            "id": reference_id,
            "title": item.title,
            "section": item.section,
            "excerpt": item.excerpt,
            "category": item.category.value,
            "evidence_level": item.evidence_level.value,
            "limitations": item.limitations,
        }
        for reference_id, item in knowledge_catalog.items.items()
    ]
    return _redact_tree(payload)


def provider_tool_schema(definition: AgentToolDefinition) -> dict[str, Any]:
    if not definition.read_only:
        raise ValueError("Write-capable tools cannot be exposed to a provider.")
    schema = json.loads(json.dumps(definition.input_schema))
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    return {
        "type": "function",
        "function": {
            "name": definition.name,
            "description": definition.description[:500],
            "parameters": schema,
            "strict": True,
        },
    }


class OpenAICompatibleAgentGateway(AgentLLMGateway):
    """Strict structured adapter for OpenAI-compatible Chat Completions."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[Settings, str], Any] | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.settings = settings
        allow_local = (
            settings.app_env.lower() == "development"
            and settings.coach_agent_allow_local_provider_in_development
        )
        self.base_url = validate_provider_base_url(
            settings.coach_agent_base_url,
            allow_local_development=allow_local,
        )
        self._client_factory = client_factory or self._default_client
        self._sleeper = sleeper
        self._client: Any | None = None
        self.last_usage = AgentProviderUsage()
        self.last_reliability = ProviderCallReliability(
            attempts=0,
            max_attempts=settings.coach_agent_max_retries + 1,
            failure_category=None,
            retried=False,
            final_status="NOT_CALLED",
        )
        self.last_response_metadata: dict[str, Any] = {}

    @staticmethod
    def _default_client(settings: Settings, base_url: str) -> Any:
        import httpx
        from openai import OpenAI

        timeout = httpx.Timeout(
            timeout=settings.coach_agent_total_timeout_seconds,
            connect=settings.coach_agent_connect_timeout_seconds,
            read=settings.coach_agent_read_timeout_seconds,
        )
        http_client = httpx.Client(timeout=timeout, follow_redirects=False)
        return OpenAI(
            api_key=settings.coach_agent_api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
            http_client=http_client,
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory(self.settings, self.base_url)
        return self._client

    @staticmethod
    def _error_code(category: ProviderFailureCategory) -> AgentErrorCode:
        if category == ProviderFailureCategory.PROVIDER_RATE_LIMIT:
            return AgentErrorCode.AGENT_PROVIDER_RATE_LIMITED
        if category in {
            ProviderFailureCategory.PROVIDER_INVALID_RESPONSE,
            ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            ProviderFailureCategory.PROVIDER_TOOL_PROTOCOL_ERROR,
            ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED,
            ProviderFailureCategory.PROVIDER_EMPTY_CONTENT,
            ProviderFailureCategory.PROVIDER_INVALID_JSON,
        }:
            return AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID
        return AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE

    def _retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.settings.coach_agent_max_retries,
            initial_backoff_seconds=self.settings.coach_agent_retry_initial_backoff_seconds,
            max_backoff_seconds=self.settings.coach_agent_retry_max_backoff_seconds,
        )

    def _response_format(self, intent: AgentIntent) -> dict[str, Any]:
        if self.settings.coach_agent_response_format_mode == "json_object":
            return {"type": "json_object"}
        schema = (
            ProviderTodayModelOutput
            if intent == AgentIntent.TODAY_RECOMMENDATION
            else ProviderAgentModelOutput
        )
        return {
            "type": "json_schema",
            "json_schema": {
                "name": (
                    "provider_today_output"
                    if intent == AgentIntent.TODAY_RECOMMENDATION
                    else "agent_model_output"
                ),
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        }

    def _request(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        intent: AgentIntent,
        max_output_tokens: int | None = None,
    ) -> Any:
        profile = task_model_profile(self.settings, ModelTaskType.COACH_ANALYSIS)
        request: dict[str, Any] = {
            "model": profile.model,
            "messages": copy.deepcopy(messages),
            "response_format": self._response_format(intent),
            "max_tokens": max_output_tokens or profile.max_output_tokens,
            "temperature": 0.2,
        }
        request["extra_body"] = {
            "thinking": {"type": "enabled" if profile.thinking_enabled else "disabled"}
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        return self.client.chat.completions.create(**request)

    def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _response_lengths(choice: Any) -> tuple[str | None, str, str]:
        message = choice.message
        return (
            getattr(choice, "finish_reason", None),
            getattr(message, "content", None) or "",
            getattr(message, "reasoning_content", None) or "",
        )

    @staticmethod
    def _parse_response(
        response: Any,
        intent: AgentIntent,
        context: AgentContext,
        user_message: str,
    ) -> AgentModelOutput:
        if not getattr(response, "choices", None):
            raise AgentProviderError(
                AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                category=ProviderFailureCategory.PROVIDER_INVALID_RESPONSE,
            )
        choice = response.choices[0]
        finish_reason, content_text, reasoning_text = OpenAICompatibleAgentGateway._response_lengths(choice)
        if finish_reason == "length":
            raise AgentProviderError(
                AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                category=ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning_text),
                content_length=len(content_text),
            )
        message = choice.message
        native_calls = getattr(message, "tool_calls", None) or []
        if native_calls:
            try:
                calls = []
                for item in native_calls:
                    arguments = json.loads(item.function.arguments or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("tool arguments must be an object")
                    calls.append(
                        AgentToolInvocation(
                            tool_call_id=uuid4(),
                            tool_name=item.function.name,
                            arguments=arguments,
                        )
                    )
                return AgentModelOutput(
                    intent=intent,
                    tool_calls=calls,
                    risk_level=AgentRiskLevel.UNKNOWN,
                )
            except (AttributeError, json.JSONDecodeError, TypeError, ValidationError, ValueError) as exc:
                raise AgentProviderError(
                    AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                    category=ProviderFailureCategory.PROVIDER_TOOL_PROTOCOL_ERROR,
                ) from exc
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise AgentProviderError(
                AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                category=ProviderFailureCategory.PROVIDER_EMPTY_CONTENT,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning_text),
                content_length=len(content_text),
            )
        stripped = content.strip()
        if stripped.startswith("```"):
            raise AgentProviderError(
                AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                category=ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
            )
        try:
            if intent == AgentIntent.TODAY_RECOMMENDATION:
                provider_output = ProviderTodayModelOutput.model_validate_json(stripped)
                evidence = materialize_evidence_references(
                    provider_output.key_evidence_ids,
                    context,
                )
                facts = build_authoritative_today_facts(
                    context,
                    user_message=user_message,
                    key_evidence=evidence,
                )
                return AgentModelOutput(
                    answer=provider_output.answer,
                    summary=provider_output.summary,
                    intent=AgentIntent.TODAY_RECOMMENDATION,
                    risk_level=facts.risk_level,
                    warnings=facts.warnings,
                    limitations=facts.limitations,
                    knowledge_reference_ids=provider_output.knowledge_reference_ids,
                    today_recommendation=facts.recommendation,
                )
            provider_output = ProviderAgentModelOutput.model_validate_json(stripped)
            return AgentModelOutput.model_validate(
                provider_output.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise AgentProviderError(
                AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID,
                category=ProviderFailureCategory.PROVIDER_INVALID_JSON,
            ) from exc

    @staticmethod
    def _assistant_turn(message: Any, execution_state: AgentExecutionState) -> dict[str, Any]:
        turn: dict[str, Any] = {"role": "assistant", "content": getattr(message, "content", None)}
        reasoning = getattr(message, "reasoning_content", None)
        if isinstance(reasoning, str):
            turn["reasoning_content"] = reasoning
        native_calls = getattr(message, "tool_calls", None) or []
        if native_calls:
            serialized = []
            for item in native_calls:
                provider_id = getattr(item, "id", None) or f"call_{uuid4().hex}"
                serialized.append(
                    {
                        "id": provider_id,
                        "type": getattr(item, "type", None) or "function",
                        "function": {
                            "name": item.function.name,
                            "arguments": item.function.arguments or "{}",
                        },
                    }
                )
            turn["tool_calls"] = serialized
        return turn

    @staticmethod
    def _sync_tool_results(execution_state: AgentExecutionState, context: AgentContext) -> None:
        for result in context.tool_results:
            if result.tool_call_id in execution_state.sent_tool_result_ids:
                continue
            provider_id = execution_state.provider_call_ids.get(result.tool_call_id)
            if provider_id is None:
                continue
            payload = {
                "status": result.status.value,
                "data": _redact_tree(result.data),
                "safe_error_code": result.safe_error_code.value if result.safe_error_code else None,
            }
            execution_state.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": provider_id,
                    "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                }
            )
            execution_state.sent_tool_result_ids.add(result.tool_call_id)

    def generate(
        self,
        *,
        system_instructions: str,
        user_message: str,
        context: AgentContext,
        tools: list[AgentToolDefinition],
        trace: AgentTrace,
        execution_state: AgentExecutionState | None = None,
    ) -> AgentModelOutput:
        if not self.settings.coach_agent_enabled:
            raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_DISABLED)
        if not self.settings.coach_agent_api_key:
            raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED)
        safe_context = provider_context_payload(context)
        provider_request: dict[str, Any] = {
            "request": redact_provider_text(user_message),
            "context": safe_context,
        }
        if context.intent == AgentIntent.TODAY_RECOMMENDATION:
            # Keep the most failure-prone TODAY constraints adjacent to the
            # request payload. These are server-owned and cannot be changed by
            # the client.
            provider_request["response_constraints"] = {
                "required_top_level_fields": [
                    "answer",
                    "summary",
                    "key_evidence_ids",
                    "knowledge_reference_ids",
                ],
                "narrative_style": "qualitative_only",
                "forbid_new_distance_or_duration_numbers": True,
                "forbid_plan_mutation_claims": True,
                "forbid_absolute_safety_claims": True,
            }
        elif context.intent == AgentIntent.EXPLAIN_RUNNER_STATE:
            provider_request["response_constraints"] = {
                "use_only_supplied_runner_state_facts": True,
                "forbid_calculated_or_inferred_training_numbers": True,
                "forbid_source_titles_and_knowledge_excerpts": True,
                "knowledge_reference_ids_must_match_available_ids": True,
            }
        state = execution_state or AgentExecutionState()
        tool_round = sum(1 for item in state.messages if item.get("role") == "assistant") + 1
        if not state.messages:
            state.messages.extend(
                [
                    {"role": "system", "content": system_instructions},
                    {
                        "role": "user",
                        "content": json.dumps(
                            provider_request,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
        self._sync_tool_results(state, context)
        messages = state.messages
        safe_tools = [provider_tool_schema(tool) for tool in tools if tool.read_only]
        started = perf_counter()
        trace.add_event(
            AgentTraceEventType.PROVIDER_CALL_STARTED,
            AgentTraceStatus.STARTED,
            provider_alias=self.settings.coach_agent_provider,
            model_alias=self.settings.coach_agent_model,
            response_format_mode=self.settings.coach_agent_response_format_mode,
        )
        policy = self._retry_policy()
        for attempt in range(policy.max_attempts):
            try:
                response = self._request(
                    messages=messages,
                    tools=safe_tools,
                    intent=context.intent,
                    max_output_tokens=task_model_profile(
                        self.settings, ModelTaskType.COACH_ANALYSIS
                    ).tokens_for_attempt(attempt),
                )
                output = self._parse_response(
                    response,
                    context.intent,
                    context,
                    user_message,
                )
                finish_reason, content_text, reasoning_text = self._response_lengths(response.choices[0])
                self.last_response_metadata = {
                    "task_type": ModelTaskType.COACH_ANALYSIS.value,
                    "model_profile": ModelTaskType.COACH_ANALYSIS.value,
                    "thinking_enabled": True,
                    "tool_round": tool_round,
                    "finish_reason": finish_reason,
                    "reasoning_length": len(reasoning_text),
                    "content_length": len(content_text),
                    "max_output_tokens": task_model_profile(
                        self.settings, ModelTaskType.COACH_ANALYSIS
                    ).tokens_for_attempt(attempt),
                    "retry_count": attempt,
                }
                if output.tool_calls:
                    assistant_turn = self._assistant_turn(response.choices[0].message, state)
                    native_calls = assistant_turn.get("tool_calls", [])
                    for invocation, native in zip(output.tool_calls, native_calls, strict=True):
                        state.provider_call_ids[invocation.tool_call_id] = native["id"]
                    state.messages.append(assistant_turn)
                usage = getattr(response, "usage", None)
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    completion_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                    duration_ms=duration,
                    status="SUCCEEDED",
                )
                self.last_reliability = ProviderCallReliability(
                    attempts=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=None,
                    retried=attempt > 0,
                    final_status="SUCCEEDED",
                )
                trace.add_event(
                    AgentTraceEventType.PROVIDER_CALL_COMPLETED,
                    AgentTraceStatus.SUCCEEDED,
                    duration_ms=duration,
                    provider_alias=self.settings.coach_agent_provider,
                    model_alias=self.settings.coach_agent_model,
                    response_format_mode=self.settings.coach_agent_response_format_mode,
                    prompt_tokens=self.last_usage.prompt_tokens,
                    completion_tokens=self.last_usage.completion_tokens,
                    provider_kind="chat",
                    attempt=attempt + 1,
                    max_attempts=policy.max_attempts,
                    retried=attempt > 0,
                    final_status="SUCCEEDED",
                )
                return output
            except AgentProviderError as exc:
                self.last_response_metadata = {
                    "task_type": ModelTaskType.COACH_ANALYSIS.value,
                    "model_profile": ModelTaskType.COACH_ANALYSIS.value,
                    "thinking_enabled": True,
                    "tool_round": tool_round,
                    "finish_reason": exc.finish_reason,
                    "reasoning_length": exc.reasoning_length,
                    "content_length": exc.content_length,
                    "failure_category": exc.category.value,
                    "retry_count": attempt,
                }
                failure = provider_failure(exc.category)
                if policy.can_retry(attempt=attempt, failure=failure):
                    trace.add_event(
                        AgentTraceEventType.PROVIDER_CALL_FAILED,
                        AgentTraceStatus.FAILED,
                        provider_alias=self.settings.coach_agent_provider,
                        model_alias=self.settings.coach_agent_model,
                        response_format_mode=self.settings.coach_agent_response_format_mode,
                        provider_kind="chat",
                        attempt=attempt + 1,
                        max_attempts=policy.max_attempts,
                        failure_category=exc.category.value,
                        retried=True,
                        final_status="RETRYING",
                    )
                    policy.wait(attempt=attempt, sleeper=self._sleeper)
                    continue
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    duration_ms=duration,
                    status="FAILED",
                    safe_error_code=exc.code.value,
                )
                self.last_reliability = ProviderCallReliability(
                    attempts=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=exc.category,
                    retried=attempt > 0,
                    final_status="FAILED",
                )
                trace.add_event(
                    AgentTraceEventType.PROVIDER_CALL_FAILED,
                    AgentTraceStatus.FAILED,
                    duration_ms=duration,
                    provider_alias=self.settings.coach_agent_provider,
                    model_alias=self.settings.coach_agent_model,
                    response_format_mode=self.settings.coach_agent_response_format_mode,
                    safe_error_code=exc.code,
                    provider_kind="chat",
                    attempt=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=exc.category.value,
                    retried=attempt > 0,
                    final_status="FAILED",
                )
                raise
            except Exception as exc:
                failure = classify_provider_exception(exc)
                if policy.can_retry(attempt=attempt, failure=failure):
                    trace.add_event(
                        AgentTraceEventType.PROVIDER_CALL_FAILED,
                        AgentTraceStatus.FAILED,
                        provider_alias=self.settings.coach_agent_provider,
                        model_alias=self.settings.coach_agent_model,
                        response_format_mode=self.settings.coach_agent_response_format_mode,
                        provider_kind="chat",
                        attempt=attempt + 1,
                        max_attempts=policy.max_attempts,
                        failure_category=failure.category.value,
                        retried=True,
                        final_status="RETRYING",
                    )
                    policy.wait(attempt=attempt, sleeper=self._sleeper)
                    continue
                code = self._error_code(failure.category)
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    duration_ms=duration,
                    status="FAILED",
                    safe_error_code=code.value,
                )
                self.last_reliability = ProviderCallReliability(
                    attempts=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=failure.category,
                    retried=attempt > 0,
                    final_status="FAILED",
                )
                trace.add_event(
                    AgentTraceEventType.PROVIDER_CALL_FAILED,
                    AgentTraceStatus.FAILED,
                    duration_ms=duration,
                    provider_alias=self.settings.coach_agent_provider,
                    model_alias=self.settings.coach_agent_model,
                    response_format_mode=self.settings.coach_agent_response_format_mode,
                    safe_error_code=code,
                    provider_kind="chat",
                    attempt=attempt + 1,
                    max_attempts=policy.max_attempts,
                    failure_category=failure.category.value,
                    retried=attempt > 0,
                    final_status="FAILED",
                )
                logger.warning(
                    "coach_provider_call_failed provider=%s model=%s code=%s",
                    self.settings.coach_agent_provider,
                    self.settings.coach_agent_model,
                    code.value,
                )
                raise AgentProviderError(code, category=failure.category) from exc
        raise AgentProviderError(
            AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE,
            category=ProviderFailureCategory.PROVIDER_UNKNOWN_ERROR,
        )
