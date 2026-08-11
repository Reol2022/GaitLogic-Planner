# MCP Resources：公开训练知识投影

v0.15.0-C 为 MCP 增加三个只读 Resource：`gaitlogic://knowledge/catalog`、`gaitlogic://knowledge/docs/{document_key}` 与 `gaitlogic://capabilities`。它们适合被 Host 缓存、浏览和引用；用户训练事实仍只能经带有可信身份上下文的 Tool 获取。

`catalog` 只输出文档键、标题、类别、版本、证据等级、来源标题和限制；文档 Resource 仅接受稳定的 kebab-case catalog key。`McpKnowledgeResourceService` 复用 `KnowledgeCorpusService` 的公开投影，拒绝路径遍历、任意文件、索引位置、文件哈希和 chunk 标识。

Resource 不是训练数据导出接口，也不绕开 RAG 的 canonical reference 规则。语料或索引不健康时返回安全的 `DATA_UNAVAILABLE`，不会伪造来源。
