# Dense、BM25 与 Hybrid RRF 对比 v1

同一公开 60-case 数据集、相同 Corpus、metadata filter 和最终 `top_k=4`。Hybrid 使用固定等权 `RRF(k=60)`，Dense/BM25 候选深度均固定为 8；4/8/12 仅用于 Oracle candidate coverage 诊断，未用于调参。

| Strategy | Pass cases | Recall@4 | MRR@4 | nDCG@4 | Forbidden rate | Filter violation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 60 | 0.7867 | 0.7150 | 0.6902 | 0.0500 | 0.0000 |
| BM25 | 60 | 0.9567 | 0.9233 | 0.9106 | 0.1000 | 0.0000 |
| Hybrid RRF | 60 | 0.8867 | 0.8433 | 0.8127 | 0.0833 | 0.0000 |

## Change sets

- Hybrid recovered vs Dense: 8
- Hybrid regressed vs Dense: 4
- Hybrid recovered vs BM25: 2
- Hybrid regressed vs BM25: 7
- All fail: 5

## Oracle candidate recall

`{'4': 0.963889, '8': 1.0, '12': 1.0}`

Oracle is evaluation-only: it asks whether a relevant document appeared in the union candidate set. It is not a production score or rank. If candidate recall is high while top-4 remains poor, reranking may be justified; if candidate recall is low, improve retrieval/corpus coverage first.
