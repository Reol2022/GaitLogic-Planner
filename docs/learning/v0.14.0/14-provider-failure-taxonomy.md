# Provider Failure Taxonomy

统一类别位于 `ProviderFailureCategory`：`PROVIDER_TIMEOUT`、`PROVIDER_CONNECTION_ERROR`、`PROVIDER_RATE_LIMIT`、`PROVIDER_AUTH_ERROR`、`PROVIDER_BAD_REQUEST`、`PROVIDER_SERVER_ERROR`、`PROVIDER_INVALID_RESPONSE`、`PROVIDER_SCHEMA_ERROR`、`PROVIDER_TOOL_PROTOCOL_ERROR`、`PROVIDER_EMBEDDING_DIMENSION_ERROR` 和 `PROVIDER_UNKNOWN_ERROR`。

这些类别稳定、可测试且不携带 Provider 原始文本。Chat Adapter 将 raw transport/HTTP 异常分类后转成 `AgentProviderError`；Embedding Adapter 把响应计数、维度、NaN、usage 或 schema 问题转成带 category 的 `KnowledgeEmbeddingProviderError`。两类异常仍保持既有公开 API 的安全错误码或降级行为。

Evaluation Registry 利用安全错误码把 Provider Failure 与 Business、Tool、Validator、Infrastructure failure 分开。这样 Provider 超时不会被误判为训练规则错误，检索质量 case 也不会被误判为模型不可用。
