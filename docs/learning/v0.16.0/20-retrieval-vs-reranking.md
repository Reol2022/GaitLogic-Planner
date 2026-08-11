# Retrieval 与 Reranking

Retriever 负责“把可能相关的资料找回来”，Reranker 负责“把这些已找回资料重新排序”。候选并集在 depth=8 的 Oracle 诊断中覆盖率很高，说明 Top-4 的问题适合通过排序层继续评估；这不是把历史 60 条案例当作盲测。
