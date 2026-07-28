# Coach RAG Alpha Smoke v1

本报告使用完全虚构、固定且只读的训练 Fixture，并调用真实 Chat 与 Embedding Provider。Smoke Runner 不打开数据库连接，因此业务写入为 0。MySQL 5.7/8 兼容性由独立隔离测试矩阵验证。

报告不保存原始回答、Prompt、Context、Tool Result、知识摘录、用户问题、reasoning_content 或任何凭据。

## 环境

- Chat Provider：`openai_compatible`
- Chat Model：`deepseek-v4-flash`
- Embedding Model：`Qwen/Qwen3-Embedding-0.6B`
- 数据：完全虚构

## 场景

| 场景 | Intent | 状态 | Provider | 引用数 | 通过 |
| --- | --- | --- | --- | ---: | --- |
| GENERAL | GENERAL_TRAINING_QUESTION | SUCCEEDED | SUCCEEDED | 4 | 是 |
| EXPLAIN | EXPLAIN_RUNNER_STATE | SUCCEEDED | SUCCEEDED | 3 | 是 |
| TODAY | TODAY_RECOMMENDATION | SUCCEEDED | SUCCEEDED | 2 | 是 |
| PROVIDER_DISABLED | TODAY_RECOMMENDATION | DEGRADED | DISABLED | 0 | 是 |
| KNOWLEDGE_INDEX_UNAVAILABLE | TODAY_RECOMMENDATION | DEGRADED | SUCCEEDED | 0 | 是 |
| EMPTY_RETRIEVAL | GENERAL_TRAINING_QUESTION | SUCCEEDED | SUCCEEDED | 0 | 是 |

## TODAY 确定性一致性

- data_quality：通过
- decision：通过
- planned_workout_status：通过
- risk_level：通过

## 数据与安全

- 业务写入数量：0
- Smoke Runner 数据库连接数量：0
- 未触发 Garmin；未修改训练计划；未创建长期记忆。
- Public Knowledge References 只记录公开 document ID；不记录内部请求级 Reference ID。

## 结论

Alpha Smoke 通过。

当前仍不支持 Hybrid Retrieval、Reranker、长期记忆、写工具、Weekly Review Agent 或医疗诊断。
