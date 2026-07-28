# Training Knowledge Embedding Design v1

## 1. Embedding 是什么

Embedding 把文本转换成固定维度的数值向量，使查询与知识 Chunk 可以用统一距离函数比较。文档 Embedding 用于构建索引，Query Embedding 用于查询；两者必须来自相同 Provider、模型和维度。

Embedding 不会验证训练结论是否正确，也不能替代来源、规则或 Validator。

## 2. Provider 接口

`EmbeddingProvider` 明确区分：

- `embed_documents(texts)`：按输入顺序返回批量向量；
- `embed_query(text)`：返回单条查询向量；
- `close()`：释放 HTTP Client 等资源。

所有结果包含 provider、model、dimensions、normalized、usage 和 warnings。输入为空、超长、数量不一致、维度变化、NaN、Infinity 或空向量均会失败。

## 3. Deterministic Test Provider

`DeterministicEmbeddingProvider` 使用 SHA-256 驱动的词元/相邻词元特征散列并执行 L2 归一化。

用途：

- 离线测试索引构建；
- 验证持久化、过滤和排序；
- 验证 Manifest/root hash；
- 无网络演示完整管线。

它不具备生产语义质量声明，并且在 production 环境拒绝启用。README 和评测不得把其排序结果描述为真实 RAG 效果。

## 4. OpenAI-compatible Adapter

配置完全独立于 Coach Provider：

```text
KNOWLEDGE_EMBEDDING_ENABLED
KNOWLEDGE_EMBEDDING_PROVIDER
KNOWLEDGE_EMBEDDING_API_KEY
KNOWLEDGE_EMBEDDING_BASE_URL
KNOWLEDGE_EMBEDDING_MODEL
KNOWLEDGE_EMBEDDING_DIMENSIONS
KNOWLEDGE_EMBEDDING_BATCH_SIZE
KNOWLEDGE_EMBEDDING_*_TIMEOUT_SECONDS
```

默认关闭，不继承 Coach API Key、URL 或模型。Adapter 只调用 `/embeddings`，不会调用 Chat Completions。

## 5. 网络安全

- 只允许 HTTP/HTTPS；
- URL 禁止凭据、query 和 fragment；
- 默认拒绝 localhost、回环、私网、link-local、reserved 和 metadata 地址；
- 本地地址仅在 development 且显式开启时允许；
- `httpx` 禁止跟随重定向；
- timeout 受控；
- transport/connection error、timeout、429 和 5xx 最多重试一次；
- 400、401、403 不重试；
- 不记录 Key、输入全文或完整向量。

客户端不能控制 Provider 配置。

## 6. 批处理与维度

批次大小最大128，默认32。Index Service 按 Provider 限制切分批次，不静默截断 Chunk。配置了 dimensions 时，响应必须精确匹配；未配置时，首次成功响应建立会话维度，后续变化立即失败。

远程向量会统一 L2 归一化，以便 Exact Cosine Store 使用一致得分方向。

## 7. 可重复性边界

- Corpus Determinism：同一文档和切分得到相同 Chunk/hash。
- Index Reproducibility：确定性测试 Provider 可重复得到相同向量/root hash。
- Provider Reproducibility：远程模型可能被供应商更新，即使模型名不变，也不能保证跨时间向量逐位一致。

远程索引 Manifest 会明确记录这一限制。
