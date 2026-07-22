import pytest

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
