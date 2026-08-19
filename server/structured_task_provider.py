"""Safe structured Provider calls for non-Coach model tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from planner_core.config import Settings
from server.model_tasks import TaskModelProfile
from server.observability.tracing import NOOP_TRACER, SafeTracer, active_trace_handle
from server.provider_reliability import (
    ProviderFailureCategory,
    RetryPolicy,
    classify_provider_exception,
    provider_failure,
)

T = TypeVar("T", bound=BaseModel)

SIMPLIFIED_CHINESE_OUTPUT_INSTRUCTION = (
    "All user-facing natural-language string values must be written in Simplified Chinese. "
    "Keep enum values, identifiers, dates, field names, and deterministic rule codes unchanged."
)


class StructuredTaskProviderError(Exception):
    def __init__(
        self,
        category: ProviderFailureCategory,
        *,
        finish_reason: str | None = None,
        reasoning_length: int = 0,
        content_length: int = 0,
    ) -> None:
        super().__init__(category.value)
        self.category = category
        self.finish_reason = finish_reason
        self.reasoning_length = reasoning_length
        self.content_length = content_length


@dataclass(frozen=True)
class StructuredTaskResult:
    value: BaseModel
    reasoning_content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    content_length: int
    attempts: int
    max_output_tokens: int


class StructuredTaskProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        tracer: SafeTracer | None = None,
        sleeper=sleep,
    ) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None
        self.tracer = tracer or NOOP_TRACER
        self.sleeper = sleeper

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.ai_api_key,
                base_url=self.settings.deepseek_base_url,
                timeout=self.settings.deepseek_timeout_seconds,
                max_retries=0,
            )
        return self._client

    def _release_owned_client(self) -> None:
        if not self._owns_client or self._client is None:
            return
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = None

    @staticmethod
    def _format(schema: type[BaseModel], profile: TaskModelProfile) -> dict[str, Any]:
        if profile.response_format == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": profile.task_type.value.lower(),
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        }

    @staticmethod
    def _validate_response(response: Any, schema: type[T]) -> tuple[T, str, str | None, str]:
        if not getattr(response, "choices", None):
            raise StructuredTaskProviderError(ProviderFailureCategory.PROVIDER_INVALID_RESPONSE)
        choice = response.choices[0]
        message = choice.message
        finish_reason = getattr(choice, "finish_reason", None)
        content = getattr(message, "content", None) or ""
        reasoning = getattr(message, "reasoning_content", None) or ""
        if finish_reason == "length":
            raise StructuredTaskProviderError(
                ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning),
                content_length=len(content),
            )
        if not content.strip():
            raise StructuredTaskProviderError(
                ProviderFailureCategory.PROVIDER_EMPTY_CONTENT,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning),
                content_length=0,
            )
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise StructuredTaskProviderError(
                ProviderFailureCategory.PROVIDER_INVALID_JSON,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning),
                content_length=len(content),
            ) from exc
        try:
            value = schema.model_validate(payload)
        except ValidationError as exc:
            raise StructuredTaskProviderError(
                ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
                finish_reason=finish_reason,
                reasoning_length=len(reasoning),
                content_length=len(content),
            ) from exc
        return value, reasoning, finish_reason, content

    def generate(
        self,
        *,
        profile: TaskModelProfile,
        schema: type[T],
        system_prompt: str,
        input_payload: dict[str, Any],
    ) -> StructuredTaskResult:
        if not self.settings.ai_api_key:
            raise StructuredTaskProviderError(ProviderFailureCategory.PROVIDER_AUTH_ERROR)
        policy = RetryPolicy(
            max_retries=profile.max_retries,
            initial_backoff_seconds=self.settings.coach_agent_retry_initial_backoff_seconds,
            max_backoff_seconds=self.settings.coach_agent_retry_max_backoff_seconds,
        )
        inherited_handle = active_trace_handle()
        handle = inherited_handle or self.tracer.start_trace()
        last_error: StructuredTaskProviderError | None = None
        for attempt in range(policy.max_attempts):
            max_tokens = profile.tokens_for_attempt(attempt)
            started = perf_counter()
            with self.tracer.span(
                handle,
                component="provider",
                operation=profile.task_type.value.lower(),
                metadata={
                    "operation_type": "structured_task",
                    "task_type": profile.task_type.value,
                    "model_profile": profile.task_type.value,
                    "thinking_enabled": profile.thinking_enabled,
                    "max_output_tokens": max_tokens,
                    "request_timeout_seconds": profile.request_timeout_seconds,
                    "attempt": attempt + 1,
                    "max_attempts": policy.max_attempts,
                },
                root=inherited_handle is None and attempt == 0,
            ) as span:
                try:
                    response = self.client.chat.completions.create(
                        model=profile.model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    f"{system_prompt}\n\n{SIMPLIFIED_CHINESE_OUTPUT_INSTRUCTION}"
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "input": input_payload,
                                        "output_contract": schema.model_json_schema(),
                                        "instruction": "Return one JSON object that validates against output_contract; do not return the schema itself.",
                                    },
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ),
                            },
                        ],
                        response_format=self._format(schema, profile),
                        max_tokens=max_tokens,
                        timeout=profile.request_timeout_seconds,
                        temperature=0.2,
                        extra_body={
                            "thinking": {"type": "enabled" if profile.thinking_enabled else "disabled"}
                        },
                    )
                    value, reasoning, finish_reason, content = self._validate_response(response, schema)
                except StructuredTaskProviderError as exc:
                    last_error = exc
                    span.add_metadata(
                        finish_reason=exc.finish_reason,
                        reasoning_length=exc.reasoning_length,
                        content_length=exc.content_length,
                        failure_category=exc.category.value,
                        retry_count=attempt,
                    )
                    span.set_status("FAILED", error_code=exc.category.value)
                    failure = provider_failure(exc.category)
                    if policy.can_retry(attempt=attempt, failure=failure):
                        self._release_owned_client()
                        policy.wait(attempt=attempt, sleeper=self.sleeper)
                        continue
                    self._release_owned_client()
                    raise
                except Exception as exc:
                    failure = classify_provider_exception(exc)
                    span.add_metadata(failure_category=failure.category.value, retry_count=attempt)
                    span.set_status("FAILED", error_code=failure.category.value)
                    if policy.can_retry(attempt=attempt, failure=failure):
                        self._release_owned_client()
                        policy.wait(attempt=attempt, sleeper=self.sleeper)
                        continue
                    self._release_owned_client()
                    raise StructuredTaskProviderError(failure.category) from exc
                usage = getattr(response, "usage", None)
                details = getattr(usage, "completion_tokens_details", None)
                result = StructuredTaskResult(
                    value=value,
                    reasoning_content=reasoning,
                    finish_reason=finish_reason,
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    completion_tokens=getattr(usage, "completion_tokens", None),
                    reasoning_tokens=getattr(details, "reasoning_tokens", None),
                    content_length=len(content),
                    attempts=attempt + 1,
                    max_output_tokens=max_tokens,
                )
                span.add_metadata(
                    finish_reason=finish_reason,
                    reasoning_length=len(reasoning),
                    content_length=len(content),
                    retry_count=attempt,
                    status="SUCCEEDED",
                    latency=(perf_counter() - started) * 1000,
                )
                self._release_owned_client()
                return result
        assert last_error is not None
        raise last_error
