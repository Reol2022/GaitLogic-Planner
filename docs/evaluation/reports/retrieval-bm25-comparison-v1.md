# Dense 与 BM25 Retrieval 对比 v1

## 范围

同一公开 60 条 Retrieval Dataset、同一 Corpus、相同 metadata filters 与 `top_k=4`。Dense 继续使用既有 deterministic embedding baseline；BM25 是独立、本地、无网络依赖的 `bm25_v1` 索引。本报告不包含 query 正文、chunk 正文、向量或私有评测资产。

## Dense

- Cases: 60

| Metric | Result |
| --- | ---: |
| abstention_precision | 1.0000 |
| abstention_recall | 1.0000 |
| empty_result_accuracy | 1.0000 |
| filter_violation_rate | 0.0000 |
| forbidden_document_rate | 0.0500 |
| hit_at_1 | 0.6000 |
| hit_at_3 | 0.8400 |
| hit_at_4 | 0.8600 |
| mrr_at_4 | 0.7150 |
| ndcg_at_4 | 0.6902 |
| provider_success_rate | 1.0000 |
| recall_at_1 | 0.5367 |
| recall_at_3 | 0.7667 |
| recall_at_4 | 0.7867 |

## BM25

- Cases: 60
- Index: `bm25-0e67bfe0fcd1eb4ba4938b8b`

| Metric | Result |
| --- | ---: |
| abstention_precision | 1.0000 |
| abstention_recall | 1.0000 |
| empty_result_accuracy | 1.0000 |
| filter_violation_rate | 0.0000 |
| forbidden_document_rate | 0.1000 |
| hit_at_1 | 0.8800 |
| hit_at_3 | 0.9800 |
| hit_at_4 | 0.9800 |
| mrr_at_4 | 0.9233 |
| ndcg_at_4 | 0.9106 |
| recall_at_1 | 0.7800 |
| recall_at_3 | 0.9467 |
| recall_at_4 | 0.9567 |

## Overlap

| Group | Cases |
| --- | ---: |
| Dense only success | 2 |
| BM25 only success | 11 |
| Both success | 41 |
| Both fail | 6 |

BM25 是否优于 Dense 不能由单一通过率断言；v0.16-C 应只在这些互补性、排序和失败类型证据基础上评估 Hybrid fusion。
