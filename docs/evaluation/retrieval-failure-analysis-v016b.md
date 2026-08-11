# v0.16.0-B Dense Retrieval Failure Analysis

## Scope and method

This review uses only the checked-in public 60-case retrieval dataset and the
versioned public corpus.  Dense remains the existing deterministic baseline:
43/60 cases pass and 17 retain `RETRIEVAL_FAILURE`.  Labels, queries, chunk
boundaries, filters, and `top_k=4` were not changed.

The classifications below are a review aid, not new gold labels.  They combine
the safe per-case ranks from the evaluation report with inspection of the
public case contract.  No query body, chunk body, or private evaluation asset is
copied here.

## Results

- BM25 recovered 11 of the 17 Dense failures.
- 6 Dense failures remain failures for BM25.
- BM25 introduced 2 failures among the 43 Dense successes.
- Both strategies returned no filter violations; forbidden-document rate is a
  relevance/safety metric, not a metadata-filter failure.

| Failure group | Dense failure cases | Interpretation |
| --- | ---: | --- |
| Lexical / semantic complement | 11 | BM25 recovered an expected document with stable lexical evidence; these are candidates for future fusion evaluation. |
| Semantic confusion or ambiguous relevance | 6 | Both strategies missed at least one required document or selected a competing concept within top 4.  Do not treat this as a tokenizer defect without further label review. |
| Metadata/filter issue | 0 confirmed | Category OR, tags AND, and exact language filtering were applied equally; no filter-violation case was observed. |
| Hard negative / abstention | 0 Dense failures | The public abstention cases remain correct for both strategies. |

## Dense failure breakdown

| Outcome | Case IDs |
| --- | --- |
| Recovered by BM25 | `ret_single_001`, `ret_single_007`, `ret_single_011`, `ret_multi_002`, `ret_multi_003`, `ret_multi_004`, `ret_multi_006`, `ret_multi_007`, `ret_multi_009`, `ret_multi_012`, `ret_hard_007` |
| Still failed by both | `ret_multi_008`, `ret_multi_011`, `ret_hard_001`, `ret_hard_002`, `ret_hard_004`, `ret_hard_005` |

## What this does and does not establish

BM25's recovered cases show complementarity, especially where the public
corpus contains literal terminology that the deterministic dense baseline did
not rank completely.  They do **not** prove that a Hybrid method is better:
the two Dense-only cases, ranking metrics, forbidden-document behavior, and
the six shared failures all need to be evaluated before v0.16-C chooses a
fusion method.  No case-specific aliases, query rewrites, or corpus changes
were made to increase BM25 scores.
