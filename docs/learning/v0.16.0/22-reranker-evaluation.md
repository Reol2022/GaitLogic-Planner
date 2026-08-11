# Reranker Evaluation

比较报告必须同时列出 Dense、BM25、Hybrid 与 Rerank 的 Pass、Recall@4、MRR@4、nDCG@4、Forbidden Document Rate 与 Filter Violation Rate，并显示相对 BM25/Hybrid 的 recovered、regressed cases。Provider 未配置时报告 `REAL_PROVIDER_BLOCKED`，不能伪造结果。

`python scripts/evaluate_reranker.py` 在完整配置后对冻结的公开 60 条案例执行四条真实链路：Dense、BM25、Hybrid RRF、Rerank。Rerank 固定使用 Dense top-8 与 BM25 top-8 的去重候选池、top-4 输出和 `gaitlogic_rerank_v1` instruction；它不修改 query、Corpus、标签或单例参数。报告只保留 case ID、聚合指标、safe failure category 和 Provider 成功/失败/重试/fallback 计数，不保存 query、片段正文、向量、凭据或 Provider 原始响应。
