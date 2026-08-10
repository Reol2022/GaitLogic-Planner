# v0.15-A MCP Tools

| MCP Tool | 复用的 Coach Tool | 读取内容 | 写入能力 |
| --- | --- | --- | --- |
| `get_today_plan` | `get_today_workout` | 今日计划或无计划状态 | 无 |
| `get_recent_training` | `get_recent_training` | 最多 20 条近期结构化训练事实 | 无 |
| `get_runner_state` | `get_runner_state` | 当前确定性 Runner State、证据与限制 | 无 |

`get_recent_training` 接受 `days`（1–28）和 `limit`（1–20）。另外两个 Tool 没有客户端参数。所有 Tool 都拒绝额外字段，尤其是 `user_id` 与 `email`。身份只能由 `McpExecutionContext.identity_provider` 注入。

结果由 `server/mcp/schemas.py` 严格约束。近期训练结果特意不映射 `brief_review`，避免将训练日志自由文本交给外部 Client。返回中不包含 ORM 状态、用户 ID、邮箱、数据库 URL、文件路径、密钥、Trace、Provider 原始错误、Prompt 或 reasoning content。

调用完成后 Adapter 总会 `rollback()` 并关闭其 Session；它不调用业务 `commit()`。测试同时监控 SQL 写语句与关键业务表行数，确认三个工具没有写入。

