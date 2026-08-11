# MCP 知识检索 Tool

`retrieve_training_knowledge` 位于 `server/mcp/server.py`，输入是受限的 `query`、`top_k`、`categories`、`tags` 与 `language`。它不接受 `user_id`、chunk ID、向量、index ID 或文件路径；`GaitLogicMcpServer` 对多余字段和无效筛选器作闭集校验。

`McpToolAdapter` 不实现 embedding、向量查询或排序。它直接复用现有 `RetrieveTrainingKnowledgeTool` 与 `TrainingKnowledgeRetriever`，再通过 `materialize_knowledge_references` 将内部结果还原为公共 canonical reference。输出不含 score、vector、chunk ID、索引 ID、corpus hash 或本地路径。

因此 MCP 与 Coach Agent 使用同一份检索、版本绑定和引用安全模型；索引不可用时安全失败，而非返回看似可信的空白引用。
