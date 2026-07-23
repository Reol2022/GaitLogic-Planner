from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from planner_core.config import Settings
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentTraceEventType, AgentTraceStatus
from server.agent.errors import AgentErrorCode
from server.agent.gateway import AgentLLMGateway
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.schemas import AgentProviderUsage
from server.agent.providers.security import validate_provider_base_url
from server.agent.schemas import (
    AgentContext,
    AgentModelOutput,
    AgentToolDefinition,
    AgentToolInvocation,
)
from server.agent.trace import AgentTrace

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
        self._client: Any | None = None
        self.last_usage = AgentProviderUsage()

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
    def _retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        name = type(exc).__name__.lower()
        return status == 429 or (isinstance(status, int) and status >= 500) or any(
            marker in name for marker in ("timeout", "connection")
        )

    @staticmethod
    def _error_code(exc: Exception) -> AgentErrorCode:
        status = getattr(exc, "status_code", None)
        if status == 429:
            return AgentErrorCode.AGENT_PROVIDER_RATE_LIMITED
        return AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE

    def _response_format(self) -> dict[str, Any]:
        if self.settings.coach_agent_response_format_mode == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "agent_model_output",
                "strict": True,
                "schema": AgentModelOutput.model_json_schema(),
            },
        }

    def _request(self, *, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> Any:
        if self.settings.coach_agent_thinking_mode == "enabled":
            # DeepSeek requires reasoning_content replay across thinking-mode
            # tool-call sub-turns. v0.11.0 intentionally does not implement
            # that chain, so fail closed instead of sending an unsafe partial
            # thinking request.
            raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE)
        request: dict[str, Any] = {
            "model": self.settings.coach_agent_model,
            "messages": messages,
            "response_format": self._response_format(),
            "max_tokens": self.settings.coach_agent_max_output_tokens,
            "temperature": 0.2,
        }
        if self.settings.coach_agent_thinking_mode == "disabled":
            request["extra_body"] = {"thinking": {"type": "disabled"}}
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
    def _parse_response(response: Any, intent: AgentIntent) -> AgentModelOutput:
        if not getattr(response, "choices", None):
            raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
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
                raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID) from exc
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        stripped = content.strip()
        if stripped.startswith("```"):
            raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID)
        try:
            return AgentModelOutput.model_validate_json(stripped)
        except (ValidationError, ValueError) as exc:
            raise AgentProviderError(AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID) from exc

    def generate(
        self,
        *,
        system_instructions: str,
        user_message: str,
        context: AgentContext,
        tools: list[AgentToolDefinition],
        trace: AgentTrace,
    ) -> AgentModelOutput:
        if not self.settings.coach_agent_enabled:
            raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_DISABLED)
        if not self.settings.coach_agent_api_key:
            raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED)
        safe_context = provider_context_payload(context)
        messages = [
            {"role": "system", "content": system_instructions},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "request": redact_provider_text(user_message),
                        "context": safe_context,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ]
        safe_tools = [provider_tool_schema(tool) for tool in tools if tool.read_only]
        started = perf_counter()
        trace.add_event(
            AgentTraceEventType.PROVIDER_CALL_STARTED,
            AgentTraceStatus.STARTED,
            provider_alias=self.settings.coach_agent_provider,
            model_alias=self.settings.coach_agent_model,
            response_format_mode=self.settings.coach_agent_response_format_mode,
        )
        attempts = self.settings.coach_agent_max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._request(messages=messages, tools=safe_tools)
                output = self._parse_response(response, context.intent)
                usage = getattr(response, "usage", None)
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    completion_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                    duration_ms=duration,
                    status="SUCCEEDED",
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
                )
                return output
            except AgentProviderError as exc:
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    duration_ms=duration,
                    status="FAILED",
                    safe_error_code=exc.code.value,
                )
                trace.add_event(
                    AgentTraceEventType.PROVIDER_CALL_FAILED,
                    AgentTraceStatus.FAILED,
                    duration_ms=duration,
                    provider_alias=self.settings.coach_agent_provider,
                    model_alias=self.settings.coach_agent_model,
                    response_format_mode=self.settings.coach_agent_response_format_mode,
                    safe_error_code=exc.code,
                )
                raise
            except Exception as exc:
                if attempt + 1 < attempts and self._retryable(exc):
                    continue
                code = self._error_code(exc)
                duration = (perf_counter() - started) * 1000
                self.last_usage = AgentProviderUsage(
                    duration_ms=duration,
                    status="FAILED",
                    safe_error_code=code.value,
                )
                trace.add_event(
                    AgentTraceEventType.PROVIDER_CALL_FAILED,
                    AgentTraceStatus.FAILED,
                    duration_ms=duration,
                    provider_alias=self.settings.coach_agent_provider,
                    model_alias=self.settings.coach_agent_model,
                    response_format_mode=self.settings.coach_agent_response_format_mode,
                    safe_error_code=code,
                )
                logger.warning(
                    "coach_provider_call_failed provider=%s model=%s code=%s",
                    self.settings.coach_agent_provider,
                    self.settings.coach_agent_model,
                    code.value,
                )
                raise AgentProviderError(code) from exc
        raise AgentProviderError(AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE)
