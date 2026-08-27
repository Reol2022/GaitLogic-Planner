# Retrieval 32/60 统一工作区调查

## 结论

当前 32/60 不是检索实现回归，而是旧 `retrieval-cases-v1` / agent regression baseline
与扩充后的 corpus 不再处于同一个冻结评测版本。不得直接修改 expected result、降低
gate 或覆盖旧 baseline。

## 可复现实验

| 条件 | Corpus root | 文档 / Chunk | Recall@4 | MRR@4 | NDCG@4 |
|---|---|---:|---:|---:|---:|
| 冻结 corpus + 当前代码 | `d12cdbd31c7b6eb5b4b122f5ed686dc08495b800bb90e16dfe2544347af032df` | 12 / 60 | 0.786667 | 0.715000 | 0.690180 |
| 当前 corpus + 当前代码 | `57a90da48ef857040ee88c41f1888448fd2a684c4b34268382ace153c979df0f` | 52 / 304 | 0.506667 | 0.473333 | 0.448553 |

冻结 corpus 使用当前代码复跑后逐项恢复 `agent-regression-baseline-1.0.0` 的 Retrieval
指标，证明 embedding、Exact Dense 检索、metadata filter 和指标计算没有发生代码级
漂移。

## 当前配置

- Agent regression provider：`deterministic-sha256-v1`
- Evaluation dimensions：64
- Dense backend：Exact
- Strategy：Dense with metadata
- TopK：4
- BM25：本次 agent regression 未启用；冻结参数为 `bm25_v1`, `k1=1.2`, `b=0.75`
- Hybrid：本次未启用；冻结参数为等权 RRF，候选深度 8/8，`rrf_k=60`
- Reranker：本次未启用；冻结候选模型为 `Qwen/Qwen3-Reranker-0.6B`
- 当前 manifest 文件 SHA-256：`29daa3f02a1e369c7c4b59a5aa4f54af343548bc72dc30813cbf2b4256de154a`
- 当前 source manifest SHA-256：`49c7a4d31c71042bbc51ef95bef01b9123bab61ec4057062d7e79abcacd83a93`

## Failure Breakdown

- Expected document no longer exists：0；旧标签引用的 12 个文档仍在 corpus。
- Metadata/filter regression：0；`filter_violation_rate=0`。
- Forbidden-document regression：0；当前 `forbidden_document_rate=0`。
- Provider failure：0；`provider_success_rate=1`。
- 冻结 baseline 已有失败：14 个仍失败，属于历史 baseline 行为。
- Corpus 扩充后新增排名失败：14 个。
- Corpus 扩充后从旧失败恢复：3 个。

新增失败的结果中，大量 Top4 被新 Daniels 文档占据，例如 interval、long run、taper、
threshold、periodization 和 load-management 主题。旧 fixture 只把原始 12 文档标为相关，
没有标注这些新增但语义相关的文档，因此同时属于：

1. Corpus expansion ranking shift；
2. Evaluation fixture / baseline version mismatch。

## 后续决策

保留旧 baseline 作为 12 文档 corpus 的不可变发布证据。为 52 文档 corpus 建立新的、人工
审核相关性标签和 holdout 后，另行发布版本化 baseline；不能用当前 60-case expected
直接判定新 corpus 的发布质量。

