# Training Knowledge Retrieval Evaluation v1

## Scope

- Dataset: `retrieval-cases-v1`
- Dataset SHA-256: `aa354fb26a3951b095c3ad28cc28ed7baaa83d42447d8d19976521e9bc6cae54`
- Corpus root: `58bae62329a833c7a2a2a79dc12d31ac8c1b8052144597c839700e4b18894a7b`
- Index: `knowledge-284cf2f898d681b77d53c5fc`
- Provider/model: `deterministic_test` / `deterministic-sha256-v1`
- Execution: offline/fake provider
- Mode: `DENSE_WITH_METADATA`
- Cases: 60
- Raw answers saved: **No**
- Generated at: 2026-07-27T10:32:14.851462+00:00
- Result hash: `76a713925e9da4bb2c4259c498731a8ad4bb254d8de52503de6b9b87da939be0`

## Metrics

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
| recall_at_1 | 0.5367 |
| recall_at_3 | 0.7667 |
| recall_at_4 | 0.7867 |

## Failed cases

ret_single_001, ret_single_007, ret_single_011, ret_multi_002, ret_multi_003, ret_multi_004, ret_multi_006, ret_multi_007, ret_multi_008, ret_multi_009, ret_multi_011, ret_multi_012, ret_hard_001, ret_hard_002, ret_hard_004, ret_hard_005, ret_hard_007

## Known limitations

- deterministic_test controls reproducibility only and is not evidence of semantic retrieval quality.

## Reproduce

Run `python scripts/evaluate_training_knowledge.py retrieval` from
the repository root. Real-provider runs require server-side environment settings;
API keys are never command-line arguments or report fields.

## Safety boundary

The report contains case identifiers, ranked chunk/document identifiers, scores,
safe validation codes, and aggregate metrics only. It excludes raw provider
answers, prompts, contexts, tool results, vectors, credentials, and identities.
