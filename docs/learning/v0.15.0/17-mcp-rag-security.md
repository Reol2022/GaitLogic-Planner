# MCP RAG 安全边界

MCP 只能返回 canonical public knowledge reference：文档、章节、来源、版本、证据等级、受限摘录及限制。禁止返回内部 chunk、余弦分数、embedding、索引/语料路径、哈希、数据库信息或 Provider 原始内容。

所有 trace metadata 和 metric labels 只允许 primitive、tool/resource 名称、transport、状态、失败分类与结果数量。它们不包含 Query、Resource 正文、训练内容、用户身份或向量。Trace 和 Metrics Sink 均为 best-effort：故障会记录安全内部日志，不影响 Tool 或 Resource 的业务结果。
