"""Local, interactive MCP OAuth probe. Never prints tokens or training records."""
from __future__ import annotations

import base64
import hashlib
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

BASE = "http://127.0.0.1:18765"
CALLBACK = "http://127.0.0.1:18766/callback"


def main() -> None:
    code_holder: dict[str, str] = {}
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            params = parse_qs(urlsplit(self.path).query)
            if urlsplit(self.path).path == "/callback" and params.get("state") == [state] and params.get("code"):
                code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("授权已完成，可以关闭此页面。".encode("utf-8"))
            else:
                self.send_error(400)

        def log_message(self, *_args: object) -> None:
            pass

    with HTTPServer(("127.0.0.1", 18766), Handler) as callback, httpx.Client(timeout=30, trust_env=False) as client:
        callback.timeout = 300
        unauth = client.post(BASE + "/mcp", json={})
        unauth.raise_for_status() if unauth.status_code != 401 else None
        resource = client.get(BASE + "/.well-known/oauth-protected-resource/mcp")
        resource.raise_for_status()
        metadata = client.get(BASE + "/.well-known/oauth-authorization-server/oauth")
        metadata.raise_for_status()
        info = metadata.json()
        assert resource.json()["resource"] == BASE + "/mcp"
        assert info["issuer"] == BASE + "/oauth"
        registration = client.post(info["registration_endpoint"], json={"client_name": "GaitLogic local MCP probe", "redirect_uris": [CALLBACK]})
        registration.raise_for_status()
        client_id = registration.json()["client_id"]
        params = {"response_type": "code", "client_id": client_id, "redirect_uri": CALLBACK, "scope": "mcp:read", "resource": BASE + "/mcp", "code_challenge": challenge, "code_challenge_method": "S256", "state": state}
        print("OAuth discovery: PASS", flush=True)
        print("请在浏览器中打开并登录授权：", info["authorization_endpoint"] + "?" + urlencode(params), flush=True)
        callback.handle_request()
        if "code" not in code_holder:
            print("OAuth authorization: BLOCKED", flush=True)
            return
        token = client.post(info["token_endpoint"], data={"grant_type": "authorization_code", "client_id": client_id, "code": code_holder["code"], "redirect_uri": CALLBACK, "code_verifier": verifier, "resource": BASE + "/mcp"})
        token.raise_for_status()
        access_token = token.json()["access_token"]
        print("PKCE / token exchange: PASS", flush=True)
        headers = {"Authorization": "Bearer " + access_token, "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2026-07-28"}
        meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}, "io.modelcontextprotocol/clientInfo": {"name": "local-probe", "version": "1"}}
        for method, params in (("tools/list", {}), ("tools/call", {"name": "get_recent_training", "arguments": {"days": 28, "limit": 20}})):
            h = {**headers, "Mcp-Method": method}
            if method == "tools/call":
                h["Mcp-Name"] = "get_recent_training"
            response = client.post(BASE + "/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": {**params, "_meta": meta}})
            response.raise_for_status()
            result = response.json().get("result", {})
            if result.get("isError"):
                print(method + ": FAILED", flush=True)
                return
            if method == "tools/list":
                print("tools/list: " + ("PASS" if any(t.get("name") == "get_recent_training" for t in result.get("tools", [])) else "FAIL"), flush=True)
            else:
                content = result.get("structuredContent", {})
                data = content.get("data") or {}
                print("get_recent_training: " + str(content.get("status", "UNKNOWN")), flush=True)
                print("records_returned=" + str(len(data.get("items", []))) + " details_complete=" + str(data.get("details_complete")), flush=True)


if __name__ == "__main__":
    main()
