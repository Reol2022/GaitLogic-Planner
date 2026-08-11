# Reranker 面试要点

1. 为什么先召回再重排？Cross-Encoder 成本更高，只应处理小候选池。
2. 为什么 Provider 只能返回 index？标题、来源、引用必须仍由本地 Canonical Catalog 生成，防止来源注入。
3. Provider 挂了怎么办？回退固定 Hybrid RRF，并在 Trace 中标记 fallback，不影响训练事实和规则。
4. 为什么默认仍是 Dense？外部 Reranker 尚需独立真实 Provider 评测和新的 holdout；不能因为旧 benchmark 一次漂亮结果就切生产默认。
