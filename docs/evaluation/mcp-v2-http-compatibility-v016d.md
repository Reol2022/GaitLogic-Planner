# MCP Python SDK 2.0 HTTP compatibility diagnosis

## Scope

This note records the v0.16.0-D compatibility repair for the GaitLogic remote
MCP endpoint. The checked runtime is MCP Python SDK `2.0.0`, using the
2026-07-28 Streamable HTTP contract. It contains no authentication token,
request body, user data, or provider data.

## Observed failure

The initial regression had twelve HTTP failures. The safe request facts were:

| Field | Observed value |
| --- | --- |
| HTTP method | `POST` |
| endpoint | `/mcp` |
| Origin present | yes |
| Origin host | `mcp-client.example.test` |
| Host | `testserver` |
| MCP protocol headers | absent in the legacy test setup |
| response | `403` / `INVALID_ORIGIN` |
| response source | GaitLogic outer HTTP security middleware |

The failure was not returned by the MCP SDK transport. The test fixture passed
`mcp_allowed_hosts` and `mcp_allowed_origins` as normal Pydantic constructor
arguments. Those settings use validation aliases, so the fixture silently kept
the default allowlists instead of the fictional test allowlist. The legitimate
test Origin therefore failed the GaitLogic allowlist before authentication or
MCP routing.

## Repair

The fixture now supplies the actual environment aliases:

```python
Settings(
    MCP_ALLOWED_HOSTS="testserver",
    MCP_ALLOWED_ORIGINS="https://mcp-client.example.test",
    MCP_HTTP_ENABLED=True,
)
```

The HTTP tests now use an independent modern POST for every JSON-RPC operation.
Each request contains the required `MCP-Protocol-Version` and `Mcp-Method`
headers and the matching per-request `_meta` protocol version and client
capabilities envelope. Name-bearing requests also carry `Mcp-Name`.

The tested modern operations are `tools/list`, `tools/call`, `resources/read`,
and `prompts/get`. No modern assertion performs `initialize`, reads or writes
`Mcp-Session-Id`, or relies on a GET/SSE stream. The SDK still owns any legacy
compatibility behavior; GaitLogic does not depend on it.

## Origin and authentication policy

The policy is intentionally unchanged:

- an Origin that is present but outside the exact allowlist returns `403
  INVALID_ORIGIN` before authentication;
- a valid Origin continues to bearer authentication;
- a missing Origin is allowed to continue through host and bearer-token checks,
  which supports standard non-browser MCP clients without treating absence as a
  cross-origin browser request;
- missing or invalid bearer credentials still return the existing safe `401`
  category.

There is no wildcard Origin, authentication bypass, or test-only production
backdoor.

## Dependency reproducibility

The repository has no Python lock file. The previous range `mcp>=2.0,<3.0`
could resolve a later 2.x release with a changed protocol implementation. This
repair therefore pins the runtime-tested SDK to `mcp==2.0.0`. Future MCP SDK
upgrades require an explicit dependency change and a repeat of this compatibility
suite before release.

## Verification

- `tests/test_mcp_http.py`: modern POST, origin, authentication, identity,
  resource, prompt, trace, metrics, and failure-isolation coverage.
- `tests/test_mcp_server.py`: in-process SDK client and stdio protocol smoke.
- `python scripts/evaluate_agent.py --suite mcp`: passed after the repair.

The official Streamable HTTP transport specification requires validation of a
present Origin and specifies a single endpoint with independent POST requests.
See the [MCP Streamable HTTP specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/streamable-http.mdx)
and the [MCP Python SDK release notes](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/whats-new.md).
