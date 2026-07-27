# 10｜Agent 与 AI 应用实现

## 已完成：v0.11.0 Coach Agent

Coach Agent 的目标不是取代训练规则，而是在受控事实之上给出解释。公共入口是 `POST /api/coach/query`，当前只开放：

- `TODAY_RECOMMENDATION`
- `EXPLAIN_RUNNER_STATE`
- `GENERAL_TRAINING_QUESTION`

不开放 Weekly Review Agent、写工具、训练计划自动修改、长期记忆、Streaming、多 Agent 或文件上传。

## 架构

```text
认证用户
→ CoachAgentQueryService
→ AgentTrainingContextBuilder
→ 8 个只读 Tools
→ GaitLogicCoachAgent
→ OpenAI-compatible Gateway
→ Pydantic Provider Schema
→ Deterministic Validator
→ 公共响应或 Deterministic Fallback
```

关键文件：`server/agent/orchestrator.py`、`registry.py`、`training_context_builder.py`、`validator.py`、`fallback.py`、`providers/openai_compatible.py`、`server/services/coach_agent_query_service.py`。

## 八个只读工具

| Tool | 作用 |
| --- | --- |
| `get_runner_state` | 当前确定性跑者状态 |
| `get_runner_state_history` | 有界历史快照摘要 |
| `get_recent_training` | 近期训练事实 |
| `get_today_workout` | 今日计划 |
| `get_current_training_cycle` | 当前周期与训练块 |
| `get_training_rules` | 已公开规则 |
| `evaluate_today_workout` | 今日确定性评估 |
| `get_training_data_quality` | 训练数据质量 |

模型不直接持有数据库 Session；Tool Dependencies 由服务端用当前用户创建。Registry 校验工具是否注册、是否只读、是否允许当前 Intent，并校验输入和输出 Schema。

## 结构化输出与安全

- Provider 配置只在服务端 Settings 中存在。
- `thinking` 仅可为 `unset`、`disabled`、`enabled`；当前只支持 DeepSeek-compatible 的 disabled 请求，不回放 reasoning_content。
- `response_format` 仅可为 `json_schema` 或 `json_object`；不允许任意 extra body。
- Provider 原始回答、Prompt、Context、Token、Key 不写入公开响应或评测报告。
- Validator 拒绝医疗诊断、自动改计划、敏感信息、无效工具参数、无依据 Evidence 和不安全 TODAY 输出。

## TODAY 权威事实协议

服务端生成并拥有：decision、planned workout status、risk level、data quality、warnings、limitations、canonical key evidence。模型只生成 answer、summary 和 `key_evidence_ids`。Evidence ID 必须来自本次请求的服务端目录；最终文本由服务端恢复。

这一层解决的不是“模型 JSON 写得是否漂亮”，而是“模型不能篡改训练事实与确定性结论”。

## Provider 降级

Provider 未启用、未配置、失败或输出被拒绝时，`CoachAgentQueryService` 使用 `DeterministicCoachFallback` 返回 `DEGRADED`。它仍使用当前上下文，但不宣称模型解释成功。

## Evaluation

`server/agent/evaluation/` 的固定 32 案例评测使用虚构用户和 DeterministicEvaluationGateway。它验证工具、决策、警告、限制与越权声明，不能替代真实用户评测或开放域安全证明。

## RAG 状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| Corpus Foundation | 已提交、未发布 | 文档、来源、Chunk、Manifest/root hash |
| Embedding/Vector/Retriever | 工作区开发中 | Provider、Index、Exact Cosine、Retriever |
| Agent Tool Integration | 规划中 | 不存在 `retrieve_training_knowledge` 正式 Tool |
| RAG Evaluation / UI | 规划中 | 尚无公开用户能力 |

因此 v0.11.0 的 Coach Agent 不使用 RAG；任何面试或 README 描述都必须保留这个事实。
