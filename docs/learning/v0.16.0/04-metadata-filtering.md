# Metadata Filter 与公共引用

检索请求中的 Filter 仅允许已有的训练知识分类、标签和语言。Exact 与 Qdrant 使用同一 `RetrievalFilters` Schema：

- `categories`：命中任意一个分类；
- `tags`：文档必须包含请求中的全部标签；
- `language`：与请求语言完全一致。

Qdrant 的 Filter 由显式 `FieldCondition` 构造，不接受客户端提供任意 payload key 或 Qdrant 原生表达式。这样客户端不能借检索接口探测未设计为公开 metadata 的字段。

Vector Store 的结果只返回 `chunk_id` 和分数。Retriever 再以 `chunk_id` 在已验证 Corpus 中取得 Canonical Knowledge Reference，因此用户看到的引用、标题、证据等级、版本和摘要都有唯一权威来源。Qdrant payload 不承担事实解释，也不能绕过 Canonical Reference 的物化过程。
