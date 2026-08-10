# Evaluation Metrics

Coach 侧保留 Intent Accuracy、Required Tool Recall、Tool Argument Validity、Decision Consistency、Warning/Limitation Retention、Fallback Success、Unsupported Claim 和 Rule Violation 等既有指标。它们验证模型编排和确定性边界是否仍被遵守。

RAG 侧保留 Canonical Evidence Accuracy、Knowledge Tool Success、Citation Precision/Recall、Source Hallucination、Decision Invariance 和 Unauthorized Plan Modification。TODAY 的确定性事实不由 RAG 决定，因此 Decision Invariance 是关键安全指标。

Retrieval 使用 Recall@K、MRR@K、nDCG@K、Forbidden Document Rate 与 Filter Violation。Recall@K 衡量前 K 个结果是否覆盖相关文档；MRR@K 衡量首个相关文档排得多靠前；nDCG@K 结合相关性等级衡量排序质量。这些不能与 Coach 的 Case Pass Rate 横向相加。

Weekly Adaptive 保留 Weekly Facts Accuracy、Rule Consistency、Unsupported Fact Rate、Proposal Rule Violation、Rollback Success 与 Fallback Success。写入、幂等和回滚的专门 MySQL 集成测试仍是它们的重要证据，离线 case runner 不伪造写操作。
