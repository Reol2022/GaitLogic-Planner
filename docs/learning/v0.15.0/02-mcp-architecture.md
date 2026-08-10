# MCP 架构

```text
MCP Host / Client
        ↓ stdio
server.mcp.server (MCPServer)
        ↓
McpToolAdapter
        ↓
Coach Agent request-scoped Tool Registry
        ↓
Existing GaitLogic Services
        ↓
SQLAlchemy / MySQL
```

`server/mcp/server.py` 只负责协议注册和参数边界；`server/mcp/adapters.py` 不写 SQL、不重算 Runner State。它通过 `CoachAgentToolDependencies.from_session()` 和 `build_coach_agent_tool_registry()` 调用已验证的 `get_today_workout`、`get_recent_training`、`get_runner_state`，随后将数据映射成 MCP 公共 Schema。

每一次工具调用使用：

```text
mcp.request → mcp.tool → tool.invoke → existing service
```

`McpRequestIdentity` 只存在于服务器内部执行上下文。它没有出现在 Tool 参数、MCP 结果或 Trace metadata 中。直接用 `python -m server.mcp.server` 启动时没有身份，因此能 `tools/list`，但所有用户数据读取均返回 `AUTH_CONTEXT_MISSING`。这是 v0.15-A 的刻意安全默认值。

