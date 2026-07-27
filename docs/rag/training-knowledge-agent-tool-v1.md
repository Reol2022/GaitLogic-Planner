# Training Knowledge Agent Tool v1

## 目标

`retrieve_training_knowledge` 将 v0.12.0-B 的结构化 Retriever 接入 Coach
Agent。它只读取版本化训练知识，不读取用户训练数据、不连接业务数据库、不调用
Chat Completion，也不生成或修改训练决策。

训练事实与训练知识保持分离：

- Runner State、今日计划、训练日志和规则结果属于 Training Facts；
- 语料 Chunk、来源和训练原理属于 Training Knowledge；
- TODAY 的 decision、risk、planned status、data quality、warnings、
  limitations 和 Evidence 始终由确定性服务拥有；
- RAG 只能解释这些既有事实。

## Tool Schema

工具允许三个公开 Intent：

- `TODAY_RECOMMENDATION`
- `EXPLAIN_RUNNER_STATE`
- `GENERAL_TRAINING_QUESTION`

输入字段为 `query`、`top_k`、`categories`、`tags`、`language`。Schema
`extra="forbid"`，不接受 `user_id`、Provider、模型、索引路径或任意 metadata
filter。`top_k` 的公开范围为 1～6，服务端配置还会进一步限制最终数量。

输出包含查询状态、索引 ID、Corpus root hash 和最多六条结果。每条结果具有请求级
`knowledge_n`、Canonical Chunk 标识、标题、章节、受限 excerpt、来源元数据和
score。它不包含向量、完整文档、绝对路径或用户数据。

## 执行生命周期

1. Query Service 根据服务端配置决定是否注册工具；
2. Provider 只能从 Registry 获得已启用工具；
3. Tool 在执行时创建 Retriever；
4. Retriever 验证 Corpus、Index Snapshot、Provider、模型和维度绑定；
5. 只生成 Query Embedding，不重建文档向量；
6. 结果按 Retriever 排名映射为 `knowledge_1...n`；
7. 工具结果进入当前请求 Context，既不持久化也不写入普通日志。

生产配置：

```env
COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=false
COACH_AGENT_KNOWLEDGE_INDEX_ID=
COACH_AGENT_KNOWLEDGE_TOP_K=4
```

Embedding Key、Base URL 和模型仍使用独立的 `KNOWLEDGE_EMBEDDING_*` 配置，
不能继承 Coach Chat Provider 的凭据。请求期间不会自动构建索引。

## Intent Policy

### TODAY

Runner State、今日计划、近期训练、数据质量和今日规则评估先建立确定性上下文。
知识工具可选，只能解释为什么某种原则与既有结论相关。知识检索失败时，确定性
建议仍然可用。

### EXPLAIN

必须以已有 Runner State 为事实基础。知识可以解释疲劳、恢复、训练阶段或负荷
概念，但不能修改状态，也不能创造新的个人训练数字。

### GENERAL

训练理论问题可以调用知识工具。成功且非空的检索必须返回至少一个有效知识引用；
空结果或不可用必须保留 limitation，不能声称使用过知识库。

## 故障降级

关闭开关时工具不进入 Provider Tool 列表。启用后，Index 缺失、过期、损坏，
Corpus hash 或 Provider/model/dimensions 不匹配，以及 Query Embedding 异常，
都会在 Tool Registry 边界转换为安全失败，不泄露路径或异常正文。

- TODAY：返回确定性 Fallback，不改变训练结论；
- EXPLAIN：保留 Runner State 事实，不创造理论来源；
- GENERAL：可以 DEGRADED，但不生成伪造引用。

## 当前限制

- 前端尚不展示 `knowledge_references`；
- 尚未进行真实 Embedding 质量评测；
- 没有 reranker、混合检索或 RAG Evaluation；
- 一次 Agent 请求最多允许一次知识检索；
- 训练知识库不是医学知识库。
