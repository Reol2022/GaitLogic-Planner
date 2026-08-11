# MCP Authentication

原有网页登录 JWT 验证签名和过期时间，但历史 Token 没有 MCP 专用的 issuer、audience 和 purpose。直接把它用于 `/mcp` 会让 Web API 与 MCP Resource Server 共用无边界凭据，因此 v0.15.0-B 新增短期 MCP 专用 Bearer Token。

`server/services/auth_service.py` 的 `create_mcp_access_token` 签发包含 `sub`、`iss`、`aud`、`purpose=mcp`、`iat` 与 `exp` 的 HS256 JWT。`decode_mcp_access_token` 必须同时验证 header、签名、过期时间、issuer、audience、purpose 和合法 subject。普通网页登录 JWT 没有这些声明，不能访问 MCP。

已登录用户可以通过 `POST /api/auth/mcp-token` 获得短期 MCP-only Token；请求没有 user_id 参数，身份仍由已有 REST 登录依赖确定。Token 只能放在 `Authorization: Bearer ...`，不能写入 URL、日志、Provider 请求、Garmin 请求或嵌入向量请求。

当前实现应准确称为 **GaitLogic authenticated MCP HTTP mode**。它没有实现 MCP OAuth 2.1 所需的 Protected Resource Metadata、Authorization Server Discovery、授权码/PKCE 和动态客户端注册；因此不能宣称完整 MCP OAuth Authorization Specification compatibility。
