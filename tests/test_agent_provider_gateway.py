from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from planner_core.config import Settings
from server.agent.enums import AgentIntent, AgentRiskLevel
from server.agent.errors import AgentErrorCode
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.openai_compatible import (
    OpenAICompatibleAgentGateway,
    redact_provider_text,
)
from server.agent.schemas import AgentContext, AgentToolDefinition
from server.agent.trace import AgentTrace
from tests.agent_tool_fakes import NOW


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class ProviderFailure(Exception):
    def __init__(self, status_code: int):
        super().__init__("secret provider response")
        self.status_code = status_code


class ConnectTimeout(Exception):
    pass


class ReadTimeout(Exception):
    pass


def settings(**updates) -> Settings:
    values = {
        "COACH_AGENT_ENABLED": True,
        "COACH_AGENT_API_KEY": "fictional-key",
        "COACH_AGENT_BASE_URL": "https://api.example.com/v1",
        "COACH_AGENT_MODEL": "fictional-model",
        "COACH_AGENT_MAX_RETRIES": 1,
    }
    values.update({key.upper(): value for key, value in updates.items()})
    return Settings(_env_file=None, **values)


def context() -> AgentContext:
    return AgentContext(
        request_id="8c785ddb-a652-4fe4-a048-88350c183cc7",
        user_id=1001,
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        current_time=NOW,
        timezone="Asia/Shanghai",
        runner_state={"overall_state": "UNKNOWN"},
    )


def response(*, content=None, tool_calls=None, reasoning_content=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls or [],
                    reasoning_content=reasoning_content,
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150),
    )


def run_gateway(fake: FakeClient, *, configured: Settings | None = None, tools=None):
    gateway = OpenAICompatibleAgentGateway(
        configured or settings(), client_factory=lambda _settings, _url: fake
    )
    trace = AgentTrace(request_id=context().request_id)
    output = gateway.generate(
        system_instructions="safe fixed prompt",
        user_message="Explain fictional state",
        context=context(),
        tools=tools or [],
        trace=trace,
    )
    return gateway, output, trace


def test_valid_structured_output_and_json_schema_request() -> None:
    payload = {
        "answer": "The state is unknown.",
        "intent": "EXPLAIN_RUNNER_STATE",
        "risk_level": "UNKNOWN",
    }
    fake = FakeClient([response(content=json.dumps(payload))])
    gateway, output, _ = run_gateway(fake)
    assert output.answer == "The state is unknown."
    call = fake.completions.calls[0]
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in call
    assert "tool_choice" not in call
    assert gateway.last_usage.total_tokens == 150


def test_thinking_mode_unset_preserves_generic_provider_request() -> None:
    fake = FakeClient(
        [response(content=json.dumps({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}))]
    )
    run_gateway(fake, configured=settings(COACH_AGENT_THINKING_MODE="unset"))
    assert "extra_body" not in fake.completions.calls[0]


def test_thinking_mode_disabled_adds_only_controlled_extra_body() -> None:
    fake = FakeClient(
        [response(content=json.dumps({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}))]
    )
    run_gateway(
        fake,
        configured=settings(
            COACH_AGENT_THINKING_MODE="disabled",
            COACH_AGENT_EXTRA_BODY='{"unsafe":true}',
        ),
    )
    assert fake.completions.calls[0]["extra_body"] == {
        "thinking": {"type": "disabled"}
    }


def test_thinking_mode_enabled_fails_closed_before_provider_call() -> None:
    fake = FakeClient([])
    with pytest.raises(AgentProviderError) as exc:
        run_gateway(
            fake,
            configured=settings(COACH_AGENT_THINKING_MODE="enabled"),
        )
    assert exc.value.code == AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE
    assert fake.completions.calls == []


def test_reasoning_content_is_not_exposed_or_replayed_in_non_thinking_mode() -> None:
    payload = {
        "answer": "The final answer is safe.",
        "intent": "EXPLAIN_RUNNER_STATE",
        "risk_level": "UNKNOWN",
    }
    fake = FakeClient(
        [
            response(
                content=json.dumps(payload),
                reasoning_content="private chain of thought",
            )
        ]
    )
    _gateway, output, trace = run_gateway(
        fake,
        configured=settings(COACH_AGENT_THINKING_MODE="disabled"),
    )
    assert output.answer == "The final answer is safe."
    assert "reasoning_content" not in output.model_dump(mode="json")
    assert "private chain of thought" not in str(trace.model_dump(mode="json"))
    assert "private chain of thought" not in json.dumps(
        fake.completions.calls[0],
        ensure_ascii=False,
    )


def test_native_single_and_multiple_tool_calls_are_structured() -> None:
    native = [
        SimpleNamespace(function=SimpleNamespace(name="get_runner_state", arguments="{}")),
        SimpleNamespace(function=SimpleNamespace(name="get_training_data_quality", arguments='{"window_days":14}')),
    ]
    _gateway, output, _ = run_gateway(FakeClient([response(tool_calls=native)]))
    assert [item.tool_name for item in output.tool_calls] == [
        "get_runner_state", "get_training_data_quality"
    ]


@pytest.mark.parametrize(
    "native",
    [
        [SimpleNamespace(function=SimpleNamespace(name="get_runner_state", arguments="[]"))],
        [SimpleNamespace(function=SimpleNamespace(name="INVALID TOOL", arguments="{}"))],
    ],
)
def test_invalid_native_tool_calls_are_model_output_errors(native) -> None:
    fake = FakeClient([response(tool_calls=native)])
    with pytest.raises(AgentProviderError) as exc:
        run_gateway(fake)
    assert exc.value.code == AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID
    assert len(fake.completions.calls) == 1


@pytest.mark.parametrize(
    "content",
    ["not json", "```json\n{}\n```", '{"intent":"INVALID","answer":"x"}', '{"intent":"EXPLAIN_RUNNER_STATE","answer":"x","extra":1}'],
)
def test_invalid_output_is_rejected_without_retry(content: str) -> None:
    fake = FakeClient([response(content=content)])
    with pytest.raises(AgentProviderError) as exc:
        run_gateway(fake)
    assert exc.value.code == AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID
    assert len(fake.completions.calls) == 1


def test_retryable_429_and_500_retry_once() -> None:
    payload = json.dumps({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe", "risk_level": "UNKNOWN"})
    for status_code in (429, 500):
        fake = FakeClient([ProviderFailure(status_code), response(content=payload)])
        _gateway, output, _ = run_gateway(fake)
        assert output.answer == "safe"
        assert len(fake.completions.calls) == 2


@pytest.mark.parametrize("failure", [ConnectTimeout("secret"), ReadTimeout("secret")])
def test_connection_and_read_timeouts_retry_once(failure: Exception) -> None:
    payload = json.dumps(
        {"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe", "risk_level": "UNKNOWN"}
    )
    fake = FakeClient([failure, response(content=payload)])
    _gateway, output, _ = run_gateway(fake)
    assert output.answer == "safe"
    assert len(fake.completions.calls) == 2


def test_authentication_failure_is_not_retried() -> None:
    fake = FakeClient([ProviderFailure(401)])
    with pytest.raises(AgentProviderError) as exc:
        run_gateway(fake)
    assert exc.value.code == AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE
    assert len(fake.completions.calls) == 1


def test_overlong_output_is_rejected_without_retry() -> None:
    fake = FakeClient(
        [
            response(
                content=json.dumps(
                    {"intent": "EXPLAIN_RUNNER_STATE", "answer": "x" * 12001}
                )
            )
        ]
    )
    with pytest.raises(AgentProviderError) as exc:
        run_gateway(fake)
    assert exc.value.code == AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID
    assert len(fake.completions.calls) == 1


def test_tool_schema_is_read_only_bounded_and_forbids_extra_arguments() -> None:
    definition = AgentToolDefinition(
        name="get_runner_state",
        description="read state",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        allowed_intents=[AgentIntent.EXPLAIN_RUNNER_STATE],
    )
    fake = FakeClient([response(content=json.dumps({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}))])
    run_gateway(fake, tools=[definition])
    parameters = fake.completions.calls[0]["tools"][0]["function"]["parameters"]
    assert parameters["additionalProperties"] is False
    assert "user_id" not in parameters.get("properties", {})


def test_provider_request_removes_identity_and_redacts_contact_data() -> None:
    fake = FakeClient([response(content=json.dumps({"intent": "EXPLAIN_RUNNER_STATE", "answer": "safe"}))])
    run_gateway(fake)
    request_text = fake.completions.calls[0]["messages"][1]["content"]
    assert "1001" not in request_text
    assert "user_id" not in request_text
    assert "request_id" not in request_text


def test_provider_text_redacts_email_and_phone() -> None:
    redacted = redact_provider_text("runner@example.test 13800138000")
    assert "runner@example.test" not in redacted
    assert "13800138000" not in redacted
    assert redacted == "[REDACTED_EMAIL] [REDACTED_PHONE]"


def test_provider_error_log_omits_headers_raw_error_and_api_key(caplog) -> None:
    fake = FakeClient([ProviderFailure(500), ProviderFailure(500)])
    configured = settings(COACH_AGENT_API_KEY="fictional-secret-header")
    with caplog.at_level("WARNING"), pytest.raises(AgentProviderError):
        run_gateway(fake, configured=configured)
    logged = caplog.text
    assert "fictional-secret-header" not in logged
    assert "secret provider response" not in logged
    assert "Authorization" not in logged


def test_disabled_and_unconfigured_provider_do_not_call_client() -> None:
    fake = FakeClient([])
    for configured, code in (
        (settings(coach_agent_enabled=False), AgentErrorCode.AGENT_PROVIDER_DISABLED),
        (settings(coach_agent_api_key=None), AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED),
    ):
        with pytest.raises(AgentProviderError) as exc:
            run_gateway(fake, configured=configured)
        assert exc.value.code == code
    assert fake.completions.calls == []
