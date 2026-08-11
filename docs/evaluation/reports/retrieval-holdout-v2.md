# Retrieval Holdout v2

Independent public fictional holdout. Reports deliberately omit query text, chunks, vectors and provider payloads.

- Dataset SHA-256: `ae54a34e6c72447f4ebfe441c04104cb708da295c812452a6e460ba4a950556b`
- Case count: 40

| Strategy | Status | Pass | Recall@4 | MRR@4 | nDCG@4 | Forbidden | Filter violation | P50/P95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense_exact | COMPLETED | 33/40 | 0.936937 | 0.914414 | 0.890827 | 0.1 | 0.0 | 560.43/1151.463 |
| dense_qdrant | ENVIRONMENT_SKIPPED | N/A/N/A | N/A | N/A | N/A | N/A | N/A | N/A/N/A |
| bm25 | COMPLETED | 29/40 | 0.869369 | 0.878378 | 0.85333 | 0.05 | 0.0 | 11.281/11.786 |
| hybrid_rrf | COMPLETED | 32/40 | 0.918919 | 0.871622 | 0.85992 | 0.075 | 0.0 | 124.139/137.163 |
| rerank | COMPLETED | 33/40 | 0.932432 | 0.932432 | 0.916592 | 0.075 | 0.0 | 567.729/666.239 |

## Decision

Strategy selection is manual and must satisfy every safety gate; this report does not calculate a synthetic overall winner.
