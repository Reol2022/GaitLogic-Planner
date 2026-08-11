# Index Manifest、Freshness 与切换

`index-manifest.json` 记录 Corpus root hash、Corpus Manifest 文件哈希、Embedding Provider、Model、维度、归一化状态、Vector Store、距离度量、Chunk Count、Chunk/内容/向量哈希和创建时间。`server/knowledge_retrieval/index_manifest.py` 对整个结构计算稳定 root hash。

因此切换 `exact` 与 `qdrant` 会得到不同 Index ID：Store 类型是 Index Identity 的一部分。不会把 Qdrant 当成一个可以直接打开旧 Exact JSON 索引的替代品。

部署切换顺序应为：构建目标 Store 的新索引；执行 `knowledge_index.py validate`；更新 `COACH_AGENT_KNOWLEDGE_INDEX_ID` 与 `KNOWLEDGE_VECTOR_STORE`；执行受控查询或 readiness；最后切流。不要在运行中替换同一 Index ID。Qdrant force replacement 被刻意拒绝，以保持索引不可变和回滚明确。

回滚也很直接：恢复上一组 Index ID 和 `KNOWLEDGE_VECTOR_STORE=exact`，或关闭 Knowledge Retrieval。它不会修改数据库 schema、训练计划、Runner State 或历史快照。
