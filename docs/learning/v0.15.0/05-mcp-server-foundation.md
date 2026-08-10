# MCP Server Foundation 实现说明

入口为：

```powershell
python -m server.mcp.server
```

它只运行 `stdio` transport。SDK 的 stdout 属于 MCP JSON-RPC；本项目没有使用 `print()`，诊断只能经 stderr/logger 输出。

`GaitLogicMcpServer` 在 SDK 参数处理之前执行闭集校验。这样 SDK 默认的函数参数模型不会默默忽略未知字段；超出三个公开 Schema 的字段统一以安全 `INVALID_ARGUMENT` 拒绝。

`McpToolAdapter` 将 Agent Registry 的 `INVALID_ARGUMENTS`、`NOT_FOUND`、`NOT_ALLOWED` 和 `FAILED` 映射到 MCP 的 `INVALID_ARGUMENT`、`RESOURCE_NOT_FOUND`、`DATA_UNAVAILABLE` 和 `SERVICE_FAILURE`。客户端获得稳定 code 与简短安全 message，不会得到 Python traceback、SQL 或连接串。

SDK 的内存 `Client(server)` 用于成功调用测试；SDK stdio Client 会启动 `python -m server.mcp.server` 子进程，用于验证真正的协议启动与 stdout 纯净性。两种测试都使用虚构身份和隔离 SQLite 数据，不调用真实 Provider。

