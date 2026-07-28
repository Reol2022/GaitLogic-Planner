import pytest
from pydantic import ValidationError

from planner_core.config import Settings
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.agent.providers.security import validate_provider_base_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/provider",
        "ftp://api.example.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.9.8.7",
        "http://10.0.0.2",
        "http://192.168.1.2",
        "http://169.254.169.254/latest",
        "http://[::1]",
        "https://user:password@api.example.com",
    ],
)
def test_unsafe_provider_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_provider_base_url(url)


def test_public_https_url_is_allowed() -> None:
    assert validate_provider_base_url("https://api.example.com/v1") == "https://api.example.com/v1"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1?token=secret",
        "https://api.example.com/v1#fragment",
    ],
)
def test_provider_url_rejects_query_and_fragment(url: str) -> None:
    with pytest.raises(ValueError, match="query or fragment"):
        validate_provider_base_url(url)


def test_local_url_requires_explicit_development_override() -> None:
    assert validate_provider_base_url(
        "http://127.0.0.1:8765/v1", allow_local_development=True
    ) == "http://127.0.0.1:8765/v1"


def test_local_override_is_not_implicit() -> None:
    with pytest.raises(ValueError):
        validate_provider_base_url("http://127.0.0.1:8765/v1")


def test_gateway_allows_local_provider_only_in_explicit_development_mode() -> None:
    common = {
        "COACH_AGENT_BASE_URL": "http://127.0.0.1:8765/v1",
        "COACH_AGENT_ALLOW_LOCAL_PROVIDER_IN_DEVELOPMENT": True,
    }
    with pytest.raises(ValueError):
        OpenAICompatibleAgentGateway(
            Settings(_env_file=None, APP_ENV="production", **common)
        )
    gateway = OpenAICompatibleAgentGateway(
        Settings(_env_file=None, APP_ENV="development", **common),
        client_factory=lambda _settings, _url: object(),
    )
    assert gateway.base_url == "http://127.0.0.1:8765/v1"


def test_redirects_are_disabled_in_default_client_source() -> None:
    from inspect import getsource
    from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway

    assert "follow_redirects=False" in getsource(OpenAICompatibleAgentGateway._default_client)


@pytest.mark.parametrize("mode", ["unset", "disabled", "enabled"])
def test_thinking_mode_accepts_only_controlled_values(mode: str) -> None:
    configured = Settings(_env_file=None, COACH_AGENT_THINKING_MODE=mode)
    assert configured.coach_agent_thinking_mode == mode


def test_arbitrary_thinking_mode_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, COACH_AGENT_THINKING_MODE='{"type":"disabled"}')


def test_response_format_mode_defaults_to_json_schema() -> None:
    assert Settings(_env_file=None).coach_agent_response_format_mode == "json_schema"


@pytest.mark.parametrize("mode", ["json_schema", "json_object"])
def test_response_format_mode_accepts_only_controlled_values(mode: str) -> None:
    configured = Settings(_env_file=None, COACH_AGENT_RESPONSE_FORMAT_MODE=mode)
    assert configured.coach_agent_response_format_mode == mode


@pytest.mark.parametrize("mode", ["auto", "text", "JSON_OBJECT", " json_object", ""])
def test_arbitrary_response_format_mode_is_rejected(mode: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, COACH_AGENT_RESPONSE_FORMAT_MODE=mode)
