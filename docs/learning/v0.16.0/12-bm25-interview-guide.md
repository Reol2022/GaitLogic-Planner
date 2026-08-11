# BM25 与 RAG 面试要点

**为什么有 Embedding 仍需要 BM25？** Embedding 对语义改写友好，但精确训练术语、缩写和数字条件可能更适合词法匹配。两条独立基线能验证互补性，而不是凭直觉直接上 Hybrid。

**为什么不直接用 Qdrant 原生 BM25？** 官方 Qdrant 支持 server-side BM25，但其语言分析配置需要谨慎处理；本阶段的语料是中英混合，且目标是离线、确定性、无网络的可复现基线，因此实现了本地 BM25，同时保留未来 Sparse Adapter 的边界。

**索引如何防止过期？** `Bm25IndexManifest` 绑定 corpus hash、manifest file hash、analyzer version、BM25 参数与所有 chunk hash；校验不一致即拒绝查询。

**怎么测试？** `tests/test_bm25_retrieval.py` 覆盖构建、搜索、排序稳定性、混合语言 token、数字/缩写、过滤、过期与空结果；`tests/test_bm25_evaluation.py` 检查 60-case 对比和 Dense 独立性。

**出了什么问题？** BM25 原始分数没有上界，而既有公共 response schema 限制在 -1 到 1。修复是输出单调的 `score / (1 + score)`，而非放宽公共 schema 或把策略内部实现泄漏给前端。

**下一步为何还不能宣称 Hybrid 更好？** BM25 也产生了 Dense-only failure，且仍有 6 个共同失败。v0.16-C 必须实现独立 fusion 策略、保持 filter 与安全边界、并在相同测试集上复验。
