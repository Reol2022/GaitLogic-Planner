import json
from types import SimpleNamespace

import pytest

from planner_core.config import Settings
from server.model_tasks import ModelTaskType, task_model_profile
from server.provider_reliability import ProviderFailureCategory
from server.common.exceptions import ServiceUnavailableError
from server.services.weekly_review_ai_service import _provider_error
from server.structured_task_provider import StructuredTaskProvider, StructuredTaskProviderError
from server.weekly_review_graph.schemas import WeeklyReviewAnalysis


def settings(**values):
    return Settings(
        _env_file=None,
        AI_API_KEY="fictional",
        AI_MODEL="deepseek-v4-flash",
        AI_BASE_URL="https://api.deepseek.com",
        COACH_AGENT_RESPONSE_FORMAT_MODE="json_object",
        **values,
    )


def payload():
    return {
        "overall_assessment": "ok",
        "execution_assessment": "ok",
        "load_assessment": "ok",
        "key_session_assessment": "ok",
        "recovery_assessment": "ok",
        "intensity_assessment": "ok",
    }


def response(*, content=None, reasoning="", finish="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content, reasoning_content=reasoning))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, completion_tokens_details=SimpleNamespace(reasoning_tokens=12)),
    )


class Completions:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.values.pop(0)


class Client:
    def __init__(self, values):
        self.chat = SimpleNamespace(completions=Completions(values))


class ClosableClient(Client):
    def __init__(self, values):
        super().__init__(values)
        self.closed = False

    def close(self):
        self.closed = True


def provider(values, configured=None):
    client = Client(values)
    return StructuredTaskProvider(configured or settings(), client=client, sleeper=lambda _: None), client


def test_weekly_profile_is_thinking_and_independent_from_ai_plan_budget():
    configured = settings(
        WEEKLY_REVIEW_MAX_OUTPUT_TOKENS=15000,
        WEEKLY_REVIEW_TIMEOUT_SECONDS=310,
        PLAN_DESIGN_TIMEOUT_SECONDS=320,
        AI_PLAN_GENERATION_MAX_OUTPUT_TOKENS=24000,
    )
    weekly = task_model_profile(configured, ModelTaskType.WEEKLY_REVIEW_ANALYSIS)
    plan = task_model_profile(configured, ModelTaskType.PLAN_DESIGN)
    ai_plan = task_model_profile(configured, ModelTaskType.AI_PLAN_GENERATION)
    assert weekly.thinking_enabled and plan.thinking_enabled
    assert weekly.max_output_tokens == 15000
    assert weekly.max_output_tokens != ai_plan.max_output_tokens
    assert weekly.request_timeout_seconds == 310
    assert plan.request_timeout_seconds == 320


def test_reasoning_only_length_is_retried_with_bounded_larger_budget():
    gateway, client = provider([
        response(content="", reasoning="private reasoning", finish="length"),
        response(content=json.dumps(payload()), reasoning="private reasoning two"),
    ])
    profile = task_model_profile(settings(), ModelTaskType.WEEKLY_REVIEW_ANALYSIS)
    result = gateway.generate(profile=profile, schema=WeeklyReviewAnalysis, system_prompt="safe", input_payload={"fictional": True})
    assert result.value.overall_assessment == "ok"
    assert result.attempts == 2
    assert [item["max_tokens"] for item in client.chat.completions.calls] == [16384, 24576]
    assert [item["timeout"] for item in client.chat.completions.calls] == [300, 300]
    assert all(item["extra_body"] == {"thinking": {"type": "enabled"}} for item in client.chat.completions.calls)
    assert all(
        "Simplified Chinese" in item["messages"][0]["content"]
        for item in client.chat.completions.calls
    )


@pytest.mark.parametrize(
    ("result", "category"),
    [
        (response(content=""), ProviderFailureCategory.PROVIDER_EMPTY_CONTENT),
        (response(content="not-json"), ProviderFailureCategory.PROVIDER_INVALID_JSON),
        (response(content="{}"), ProviderFailureCategory.PROVIDER_SCHEMA_ERROR),
    ],
)
def test_validation_order_has_stable_failure_categories(result, category):
    gateway, _client = provider([result])
    profile = task_model_profile(settings(PROVIDER_TASK_MAX_RETRIES=0), ModelTaskType.WEEKLY_REVIEW_ANALYSIS)
    with pytest.raises(StructuredTaskProviderError) as exc:
        gateway.generate(profile=profile, schema=WeeklyReviewAnalysis, system_prompt="safe", input_payload={})
    assert exc.value.category == category


def test_weekly_timeout_has_specific_safe_public_message():
    error = _provider_error(
        StructuredTaskProviderError(ProviderFailureCategory.PROVIDER_TIMEOUT)
    )
    assert isinstance(error, ServiceUnavailableError)
    assert error.status_code == 503
    assert error.message == "AI 周复盘模型请求超时，请稍后重试。"


def test_owned_sdk_client_is_released_after_task_call():
    client = ClosableClient([response(content=json.dumps(payload()))])
    gateway = StructuredTaskProvider(settings(), client=client, sleeper=lambda _: None)
    gateway._owns_client = True
    profile = task_model_profile(settings(), ModelTaskType.WEEKLY_REVIEW_ANALYSIS)

    gateway.generate(
        profile=profile,
        schema=WeeklyReviewAnalysis,
        system_prompt="safe",
        input_payload={"fictional": True},
    )

    assert client.closed is True
    assert gateway._client is None
