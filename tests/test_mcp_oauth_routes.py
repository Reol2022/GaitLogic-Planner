import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from server.main import create_app


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_mcp_oauth_metadata_is_available_when_enabled(monkeypatch):
    from planner_core.config import get_settings

    monkeypatch.setenv("MCP_HTTP_ENABLED", "true")
    monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
    monkeypatch.setenv("MCP_PUBLIC_BASE_URL", "https://mcp.example.test")
    get_settings.cache_clear()
    client = TestClient(create_app())
    metadata = client.get("/.well-known/oauth-authorization-server")
    resource = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["code_challenge_methods_supported"] == ["S256"]
    assert resource.json()["resource"] == "https://mcp.example.test/mcp"
    get_settings.cache_clear()


def test_authorize_requires_registered_redirect_and_pkce(monkeypatch):
    from planner_core.config import get_settings

    monkeypatch.setenv("MCP_HTTP_ENABLED", "true")
    monkeypatch.setenv("MCP_OAUTH_ENABLED", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    registration = client.post("/oauth/register", json={"client_name": "test", "redirect_uris": ["https://chatgpt.com/callback"]})
    assert registration.status_code == 201
    response = client.get("/oauth/authorize", params={"response_type": "code", "client_id": registration.json()["client_id"], "redirect_uri": "https://chatgpt.com/callback", "scope": "mcp:read", "code_challenge": _challenge("v" * 43), "code_challenge_method": "S256"})
    assert response.status_code == 200
    assert "登录并授权" in response.text
    get_settings.cache_clear()
