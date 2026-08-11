# Dense 与 Sparse 的互补性

Dense Retrieval 使用语义向量，擅长措辞不同但意思相近的查询；BM25 擅长术语、缩写、数字与明确的字面匹配。它们都可能被多意图查询、严格多文档相关性、语料覆盖不足或 hard negative 难倒。

v0.16.0-B 的相同 60-case 测试中，Dense 为 43/60，BM25 为 52/60。两者共同成功 41，BM25-only 11，Dense-only 2，共同失败 6。这里的数字是下一阶段比较 Hybrid 的输入，不是“BM25 已取代 Dense”的结论。

当前运行时默认仍是 `KNOWLEDGE_RETRIEVAL_STRATEGY=dense`。设置为 `bm25` 时，Agent Knowledge Tool 使用独立 BM25 index；二者没有隐式融合。
