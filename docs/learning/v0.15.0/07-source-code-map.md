# v0.15-A 源码地图

| 路径 | 职责 |
| --- | --- |
| `server/mcp/server.py` | MCP SDK v2 Server、三 Tool 注册、stdio 入口与额外参数拒绝 |
| `server/mcp/context.py` | 服务器注入的身份、Session Factory、Trace 与 transport 上下文 |
| `server/mcp/adapters.py` | MCP Tool 到既有 Coach Registry 的只读适配与安全错误映射 |
| `server/mcp/schemas.py` | 公共 MCP 输入/输出与错误结构，去除训练日志自由文本 |
| `server/mcp/errors.py` | 稳定且不泄漏实现细节的错误码 |
| `server/agent/tools/factory.py` | 被复用的 Coach 八工具 Registry 工厂 |
| `server/agent/tools/dependencies.py` | 被复用的 Service 容器 |
| `server/observability/tracing.py` | Trace metadata 白名单，新增 `transport` |
| `server/observability/metrics.py` | 低基数 MCP 调用、成功、失败、延迟指标 |
| `tests/test_mcp_server.py` | 协议、身份、只读、Trace、Metrics、stdio 和回归测试 |

