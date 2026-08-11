# MCP Identity and Security

`server/mcp/http.py` 的 HTTP 安全中间件在进入 SDK 的 MCP handler 前完成三件事：校验 Origin、验证 MCP Bearer Token、从数据库读取活动用户。只有这样得到的用户才会形成 `McpRequestIdentity`，并通过 request-scoped ContextVar 注入 `McpExecutionContext`。

工具参数没有也不能有 user_id、email、role 或 tenant_id。`GaitLogicMcpServer` 对三个工具采用 closed-world 参数检查，多余字段会得到 `INVALID_ARGUMENT`。因此客户端不能借由 `{"user_id": 202}` 覆盖已经验证的 A 用户；底层 Coach Tool Registry 继续用服务端身份构造 `AgentContext`，保持既有多用户查询过滤。

Origin allowlist 使用精确 `http(s)` Origin，配置校验拒绝通配符、路径、凭据、查询串和 fragment。非法 Origin 在 Token 查库与 Tool 调用前返回 403。未认证、无效、过期和 audience 不匹配则返回安全 401，不包含 SQL、路径、Token 内容或 traceback。

HTTP 认证不传递 Token 给 Chat Provider、Embedding Provider、Garmin 或任何其他外部服务。三个 MCP Tool 仍然只读，Adapter 继续复用 Coach 的 Tool Schema、Service 和 Session rollback/close 边界。
