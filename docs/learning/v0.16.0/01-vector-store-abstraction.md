# Vector Store 抽象

代码入口是 `server/knowledge_retrieval/vector_stores/base.py` 的 `VectorStore` Protocol。它只定义五个运行时职责：构建、检索、校验、读取内部记录以复核 Manifest，以及关闭资源。

`KnowledgeIndexService` 负责从 Corpus 生成向量、建立版本化 Manifest、发布索引和 freshness 校验；`TrainingKnowledgeRetriever` 负责生成查询向量、调用 Store、再从 Canonical Corpus 物化公开结果。Store 不读取 Agent Prompt，不接触用户身份，也不生成 Coach 回答。

`server/knowledge_retrieval/vector_stores/factory.py` 是唯一的 Store 选择位置。配置值 `exact` 和 `qdrant` 会转换为固定实现身份 `exact_cosine_v1` 或 `qdrant_dense_v1`。Manifest 保存的是实现身份而不是用户输入别名，因此同一个索引不会被错误地用另一种后端打开。

这种分层让 Retriever、Tool Policy、Validator 和 TODAY 的确定性结论保持不变。替换的是“如何对已存在的查询向量排序”，而不是“哪些训练规则可以下结论”。
