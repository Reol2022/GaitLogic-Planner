# v0.16.0-C Shared Retrieval Failure Analysis

## Scope

This review uses only safe public case IDs and the checked-in 60-case dataset.
No labels, corpus documents, chunk boundaries, queries, or metadata filters were
changed.  “Shared” means Dense and BM25 both failed in v0.16.0-B; Hybrid RRF
with fixed equal weights and candidate depth 8 still fails five of those cases.

| Case ID | Hybrid outcome | Conservative review category | Reranker implication |
| --- | --- | --- | --- |
| `ret_multi_008` | Still failed | Multi-document lexical/semantic ambiguity | Inspect whether both required documents entered candidate union before adding a reranker. |
| `ret_multi_011` | Still failed | Candidate exists but rank or multi-document coverage is insufficient | Candidate recall is the deciding signal, not pass rate alone. |
| `ret_hard_001` | Still failed | Hard relevance ambiguity | Requires label/corpus review; not a tokenizer patch. |
| `ret_hard_002` | Still failed | Candidate missing or insufficient corpus coverage | A reranker cannot recover a document it never receives. |
| `ret_hard_004` | Still failed | Semantic ambiguity / ranking problem | Candidate-level inspection may justify a reranker experiment. |
| `ret_hard_005` | Recovered by Hybrid | Complementary candidates promoted by rank fusion | Evidence that fusion can help, but not proof of default readiness. |

## Oracle evidence

The evaluation-only Dense/BM25 union has Oracle Candidate Recall 0.963889 at
depth 4 and 1.0 at depths 8 and 12.  This says relevant documents are present
somewhere in the candidate union for this public dataset; it does not say RRF
placed them correctly in the final top 4.  v0.16.0-D may evaluate a reranker
only against this distinction, without changing labels or treating Oracle rank
as a production result.

## Forbidden-document review

Dense has 3 forbidden cases, BM25 has 6, and Hybrid has 5 (rates 0.05, 0.10,
and 0.083333 respectively). Hybrid suppressed `ret_hard_005` from both source
top-4 lists and suppressed BM25-only `ret_hard_003`, but promoted
`ret_hard_006` from a deeper candidate into final top 4. Hybrid therefore did
not eliminate the safety-quality issue and must not become the default. The
reported behavior is preserved rather than hard-coding forbidden IDs into
fusion. Any suspected label ambiguity should be reviewed separately and must
not be silently changed in the public dataset.
