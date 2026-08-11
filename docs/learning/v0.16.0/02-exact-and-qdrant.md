# Exact Cosine 与 Qdrant Dense 的差异

Exact Cosine 位于 `vector_stores/exact_cosine.py`。它把 `VectorRecord` 写为稳定 JSON，查询时扫描全部记录并计算精确余弦相似度。它适合小规模知识库、离线评测和可重复基线。

Qdrant 位于 `vector_stores/qdrant.py`。它使用 Qdrant 的 Cosine Collection 和 `query_points`，因此能在索引规模增长后使用 Qdrant 的检索实现。当前仍然只有一个 Dense Vector 字段：没有 sparse vector、BM25、Hybrid、Reranker 或多阶段排序。

两者均要求相同向量维度，均按 category、tags、language 执行同样的过滤语义：category 是候选集合中的任一项；tags 必须全部包含；language 必须完全相等。相同分数时 Exact 有明确的 Chunk ID 稳定排序；Qdrant 的评测通过固定公开集验证结果顺序一致。

Qdrant payload 仅保存 Chunk ID、文档标识、内容哈希和公开检索元数据。原始 Chunk 正文不进入 payload；公共 API 的标题、证据等级和 excerpt 始终从版本化 Corpus 物化，而不是信任向量库返回的内容。
