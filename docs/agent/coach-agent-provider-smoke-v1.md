# Coach Agent Provider Smoke Test v1

## 执行范围

- 执行日期：2026-07-23
- 确定性 TODAY 分离提交：`cea12f4d81451eeeddeb63d17bbdee6475901ce7`
- Provider 类型：`openai_compatible`
- Thinking mode：`disabled`
- Response format mode：`json_object`
- 数据：随机命名 MySQL 5.7 隔离库中的完全虚构训练数据

本报告不记录 API Key、Base URL、Authorization Header、Prompt、Context、工具
结果、Canonical Evidence 文本、Evidence ID 值、Provider 原始回答、Provider
request ID 或 `reasoning_content`。

## TODAY 内部协议

TODAY Provider 最终输出严格只有：

```json
{
  "answer": "Explanation only.",
  "summary": "Short explanation.",
  "key_evidence_ids": ["evidence_1"]
}
```

以下字段全部由服务端从已验证的 Context、只读工具和确定性规则装配：

- decision
- planned workout status
- risk level
- data quality
- headline
- warnings
- limitations
- Canonical key evidence

模型返回上述任一权威字段都会被 Provider 专用 Pydantic Schema 拒绝。

## 真实场景结果

| 场景 | 状态 | Provider | 说明 |
| --- | --- | --- | --- |
| `TODAY_RECOMMENDATION` | `SUCCEEDED` | `SUCCEEDED` | 服务端 decision 为 `PROCEED_WITH_CAUTION`，计划状态为 `PLANNED` |
| `EXPLAIN_RUNNER_STATE` | `SUCCEEDED` | `SUCCEEDED` | 严格 Schema 与 Validator 通过 |
| `GENERAL_TRAINING_QUESTION` | `SUCCEEDED` | `SUCCEEDED` | 严格 Schema 与 Validator 通过 |
| Provider disabled | `DEGRADED` | `DISABLED` | 确定性 Fallback 可用 |

TODAY 公开结果确认：

- data quality 为服务端确定的 `AVAILABLE`；
- risk level 为服务端确定的 `MODERATE`；
- Canonical Evidence 由请求级 ID materialize；
- 内部 `key_evidence_ids` 未进入公共响应；
- warning 和 limitation 来自服务端事实；
- Deterministic Validator 通过。

## 请求与安全验证

- `json_object` 受控配置生效；
- 每次真实请求包含 `thinking: disabled`；
- 请求没有回放 `reasoning_content`；
- 没有自动切换 response format；
- 没有 JSON 修补、宽松类型转换或第二个 LLM；
- 没有接受 `data_quality` 对象或 Union；
- 查询期间数据库业务写入次数为 0；
- 未调用 Garmin；
- 未修改训练计划；
- 未保存 Provider 原始回答；
- 未输出或记录 API Key。

## 隔离与清理

- 测试数据完全虚构；
- 使用随机命名 MySQL 5.7 隔离库；
- Smoke 结束后隔离库已删除；
- 临时 Smoke 脚本已删除；
- 未访问生产数据库。

## 结论

DeepSeek-compatible 非思考模式真实 Provider Smoke 已通过：

```text
json_object
+ Tool Calling
+ TODAY Evidence Reference
+ 服务端确定性事实装配
+ EXPLAIN
+ GENERAL
+ Provider-disabled Fallback
```

DeepSeek 兼容门槛已经清零。后续发布候选验证已在隔离 MySQL 5.7.20-log
与 MySQL 8.0.46 上分别完成完整回归，数据库矩阵结果记录在 v0.11.0 更新历史中。
