# Coach Query API v1

## 接口

`POST /api/coach/query` 是 v0.11.0-C 唯一公共 Coach 接口，必须携带现有 JWT 登录态。路由从 `get_current_user` 获取用户身份，从 `get_db` 获取请求级 Session，并把二者交给 `CoachAgentQueryService`。客户端不能提交 `user_id`、请求/Trace ID、Provider、模型、Base URL、Key、系统 Prompt 或工具定义。

请求示例使用完全虚构内容：

```json
{
  "message": "今天的已有计划是否适合执行？",
  "intent": "TODAY_RECOMMENDATION",
  "conversation_context": [
    {"role": "user", "content": "请只解释现有规则结果。"}
  ]
}
```

`message`、上下文条数、单项长度和总字符数均有上限，额外字段被拒绝。服务端生成 `user_id`、`request_id`、`trace_id`、当前时间和时区。

## Intent

当前开放：

- `TODAY_RECOMMENDATION`
- `EXPLAIN_RUNNER_STATE`
- `GENERAL_TRAINING_QUESTION`

`WEEKLY_REVIEW` 保留给 v0.11.0-D。未开放 Intent 返回 HTTP 403、结构化 `REJECTED`、安全限制说明；在此之前不加载用户训练 Context，也不调用 Provider。

## Query Service 数据流

```text
认证用户
→ 请求 Schema
→ 单用户频率/额度检查
→ 请求级 Tool Dependencies 与只读 Registry
→ AgentTrainingContextBuilder
→ Provider Gateway / 安全不可用 Gateway
→ GaitLogicCoachAgent
→ TodayRecommendationValidator
→ 公共响应或 DeterministicCoachFallback
```

Session 由 API 管理，Service 不关闭它。工具只执行 SELECT/只读 Service；Provider 调用之后不 commit、不 flush，不创建训练日志、计划、Runner State 快照或 Garmin 任务。

## 响应

公共响应包含：`request_id`、`trace_id`、`status`、`intent`、答案摘要、风险等级、可选今日建议、工具安全摘要、warnings、limitations、Provider 状态和生成时间。

`tool_calls` 只包含 `tool_name`、状态和安全错误码。响应不包含用户 ID、内部 Prompt、原始 Context、完整工具结果、Provider request ID、Token、异常正文、Trace Events 或思维链。

状态与 HTTP 语义：

- `SUCCEEDED`：200；
- `DEGRADED`：200，Provider 或校验失败但确定性降级成功；
- 业务 `UNKNOWN`：200，不代表服务器错误；
- `REJECTED`：403，Intent 未开放；
- 额度/冷却限制：429；
- `UNAVAILABLE`：503，连确定性 Context 都无法安全建立。

Provider 未启用或未配置时，只要权威工具 Context 已成功获得，接口仍返回 200 `DEGRADED`，不会返回空白或暴露配置细节。

## Quota 与 Usage

当前 AI Plan quota 与其数据库表、枚举和业务写入强耦合。为避免在“原则上不新增数据库表/迁移”的 C 阶段改变旧 AI Plan 行为，Coach 使用进程内滚动 24 小时额度与冷却保护。检查发生在 Context 和 Provider 调用前，并按内部用户 ID 隔离。

Usage 只写安全结构化运行日志：capability、Provider/模型别名、状态、输入/输出 Token 数、耗时和安全错误码。记录失败不会改变训练事实或最终回答。当前多进程部署下限额不是全局一致，这是明确限制，后续若需要全局 quota，应设计独立的通用 capability 存储，而不是复用 AI Plan 业务表硬编码。

## OpenAPI 与安全

OpenAPI 说明明确只读、非医疗。请求模型 `extra=forbid`，因此客户端不能把接口变成任意 Provider 代理。所有训练查询都从认证用户上下文派生，不允许通过参数读取其他用户数据。
