# Retrieval Strategy Selection

Strategy selection is a human decision matrix, not an automatic highest-recall switch. Hard gates include zero metadata-filter violations, zero sensitive leakage, zero Canonical Reference violations, zero source hallucination and zero Agent safety regressions. v0.16 keeps Dense Exact as default: Holdout pass count tied Rerank while Dense had higher Recall@4, lower latency and no external reranker dependency.
