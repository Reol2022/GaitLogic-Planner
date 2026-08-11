# MCP Knowledge Integration 面试要点

**为什么已有 Agent Tool Calling 还要接 MCP？** Agent Tool Calling 是 GaitLogic 内部编排能力；MCP 以标准协议向外部 Host 暴露同一批受控能力。MCP 层不能复制 SQL、Runner State 或检索排序，因此使用适配器复用现有 Service。

**Tool、Resource、Prompt 有何不同？** Tool 是参数化执行；Resource 是可发现的稳定内容；Prompt 是 Host 可复用模板。训练事实是敏感用户范围数据，不能伪装为公开 Resource。

**如何保证 RAG 不泄露内部细节？** 检索先走原 `RetrieveTrainingKnowledgeTool`，随后用 `materialize_knowledge_references` 输出 canonical reference。MCP schema 不含 vector、score、chunk ID、文件路径或 index ID。

**如何测试？** `tests/test_mcp_knowledge.py` 用完全虚构 corpus 和 Tool 验证 canonical 输出、额外参数拒绝、Resource allowlist、路径遍历拒绝、Prompt、Trace 和 Metrics。`tests/test_mcp_http.py` 保证 v0.15-B 的远程认证链路不被第四个 Tool 破坏。

**常见故障与替代方案？** 索引/语料不健康返回 `DATA_UNAVAILABLE`；不将其转换为编造引用。未来可新增经过相同公开投影和安全审计的 Resource；不应直接暴露 corpus 文件系统或向量数据库。
