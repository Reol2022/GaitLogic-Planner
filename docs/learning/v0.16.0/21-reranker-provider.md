# Reranker Provider 边界

SiliconFlow Adapter 使用官方 `/v1/rerank` 协议、`Qwen/Qwen3-Reranker-0.6B`、固定 `gaitlogic_rerank_v1` instruction 与 `return_documents=false`。外部服务只收到公开查询和候选知识片段；不会收到用户身份、Runner State、训练日志、Canonical Reference 元数据或 Trace。响应只接受现有候选的索引和有限分数。

部署时优先读取 `KNOWLEDGE_RERANKER_API_KEY`。如果它没有设置，而已配置的 OpenAI-compatible Embedding endpoint 的主机严格等于 `api.siliconflow.cn`，系统才会安全复用 `KNOWLEDGE_EMBEDDING_API_KEY`；不会从其他 Provider 或任意 URL 借用凭据。无论哪种来源，Key 都不会进入日志、Trace、Metric、测试报告或 `.env.example`。
