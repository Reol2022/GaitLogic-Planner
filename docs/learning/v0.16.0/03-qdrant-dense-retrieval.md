# Qdrant Dense Retrieval

设置 `KNOWLEDGE_VECTOR_STORE=qdrant` 后，索引构建与查询都会通过 Qdrant Adapter。`QDRANT_URL` 为空时使用受控运行目录中的本地 Qdrant；设置为无凭据、无 query 参数的 HTTP(S) URL 时使用远程 Qdrant。`QDRANT_API_KEY` 只传给 Qdrant SDK，绝不会写入 Manifest、Trace、Metric、API 响应或错误消息。

Collection 名称由受限前缀和不可变 Index ID 派生，例如 `gaitlogic_knowledge_...`。它不接受客户端指定的名称。测试使用临时目录和独立 collection；构建失败时 Adapter 只尝试删除自己在当前调用创建的 collection。

本地模式把 Qdrant 数据根放在索引版本目录同级的 `.qdrant` 目录，而不是 staging 子目录。原因是 Windows 上“临时 staging 路径 + 长 index id + collection 名称”可能超过路径长度限制。索引本身仍通过 Manifest 绑定；只有 collection 存储根被缩短。

远程 Qdrant 的连接失败、Collection 不存在和 payload 损坏都会转化为安全的 `KnowledgeVectorStoreError`，上层继续按既有知识检索降级路径处理，不暴露 URL、SQL、路径或 Provider 原始错误。
