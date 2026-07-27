# Training Knowledge Agent Integration 学习笔记

## 调用链

```text
POST /api/coach/query
→ CoachAgentQueryService
→ request-scoped Tool Registry
→ AgentTrainingContextBuilder（训练事实）
→ Provider 第一次调用
→ retrieve_training_knowledge
→ TrainingKnowledgeRetriever
→ Query Embedding + Exact Cosine Store
→ knowledge_1...n Catalog
→ Provider 第二次调用
→ AgentResponseValidator
→ Canonical Reference materialization
→ CoachQueryResponse.knowledge_references
```

## 为什么不把 Retriever 直接写进 Prompt

Prompt 不能验证 Index Snapshot、维度和 Corpus hash，也不能提供严格的输入输出
Schema。注册为 `AgentTool` 后，Registry 会依次检查 Tool 是否存在、是否只读、Intent
是否允许、参数是否有效，以及输出能否通过 Pydantic 和稳定 JSON 序列化。

## 为什么知识工具不使用数据库 Session

训练知识属于版本化公开语料，不属于用户业务数据。知识工具只依赖 Index Service、
Embedding Provider 和 Retriever。当前登录用户 ID 不会传给 Retriever，也不会成为
检索过滤条件，从而避免把知识检索错误地变成跨用户数据查询。

## Training Facts 与 Training Knowledge

TODAY 的规则结果属于事实权威，RAG 只补充解释。若知识说“疲劳时一般应降低压力”，
但今日确定性规则输出 `PROCEED_WITH_CAUTION`，模型只能解释注意事项，不能把结果改成
`REST_OR_RECOVERY`。最终 Validator 会重新核对 decision、risk、planned status 和
data quality。

## 如何增加一个知识参数

1. 修改 `RetrieveTrainingKnowledgeInput`；
2. 使用受控枚举、长度和数量限制；
3. 映射到 `KnowledgeRetrievalRequest`；
4. 补充 Provider Tool Schema 测试；
5. 验证未知字段仍被拒绝；
6. 不新增任意 metadata dict、索引路径或 Provider 参数。

## 如何排查知识引用为空

依次检查：

1. `COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED` 是否开启；
2. Index ID 是否配置；
3. `knowledge_index.py validate` 是否通过；
4. Index 的 Corpus root hash、Provider、模型和维度是否匹配；
5. Provider 是否实际调用工具；
6. Tool Result 是 `EMPTY`、失败还是成功；
7. Provider 是否返回了精确 `knowledge_n`；
8. Validator 是否因虚构来源、非法 ID 或缺少 limitation 拒绝。

不要通过打印 query、API Key、向量或完整 Provider 响应排障。

## 如何测试降级

- 关闭开关：工具不注册；
- 使用不存在的 Index ID：工具安全失败；
- 修改 Corpus Manifest：Index stale；
- 损坏 Store：校验失败；
- Fake Embedding 抛异常：Query Embedding failure；
- 返回空结果：`query_status=EMPTY`；
- TODAY 验证确定性建议仍保留；
- GENERAL 验证进入 DEGRADED 且引用为空。

自动测试使用 `deterministic_test`，只证明协议和索引链路正确，不代表真实语义检索
质量。

## 项目负责人验收清单

- [ ] 工具只允许三个公开 Intent；
- [ ] 一次请求最多一次知识检索；
- [ ] 客户端不能传 Provider、模型、索引或 user ID；
- [ ] 公共引用不含内部 ID、score、路径或向量；
- [ ] TODAY 的确定性字段不受知识影响；
- [ ] EXPLAIN 不创造个人数字；
- [ ] GENERAL 不虚构个人状态或来源；
- [ ] Index 失败不会修改数据库和训练计划；
- [ ] query、Key、向量和 Provider 原始响应不进入日志；
- [ ] 前后端和公共边界测试通过。
