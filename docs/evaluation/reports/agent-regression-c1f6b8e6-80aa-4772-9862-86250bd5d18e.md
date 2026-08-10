# GaitLogic Agent Regression Report

This report contains public fictional case identifiers, aggregate metrics, and safe error codes only.

- Run ID: `c1f6b8e6-80aa-4772-9862-86250bd5d18e`
- Baseline: `agent-regression-baseline-1.0.0`
- Provider mode: `offline`
- Overall: **PARTIAL**

## Suites

| Suite | Cases | Status |
|---|---:|---|
| coach | 32/32 | PASS |
| rag | 36/36 | PASS |
| retrieval | 43/60 | PARTIAL |
| weekly_adaptive | 32/32 | PASS |

## Regression

| Suite | Metric | Baseline | Current | Delta | Gate |
|---|---|---:|---:|---:|---|
| coach | forbidden_tool_call_rate | 0.0 | 0.0 | 0.0 | PASS |
| coach | rule_violation_rate | 0.0 | 0.0 | 0.0 | PASS |
| coach | unsupported_claim_rate | 0.0 | 0.0 | 0.0 | PASS |
| coach | warning_retention_rate | 1.0 | 1.0 | 0.0 | PASS |
| coach | case_pass_rate | 1.0 | 1.0 | 0.0 | PASS |
| coach | intent_accuracy | 1.0 | 1.0 | 0.0 | PASS |
| coach | required_tool_recall | 1.0 | 1.0 | 0.0 | PASS |
| coach | decision_consistency | 1.0 | 1.0 | 0.0 | PASS |
| coach | fallback_success_rate | 1.0 | 1.0 | 0.0 | PASS |
| rag | source_hallucination_rate | 0.0 | 0.0 | 0.0 | PASS |
| rag | rule_violation_rate | 0.0 | 0.0 | 0.0 | PASS |
| rag | unauthorized_plan_modification_rate | 0.0 | 0.0 | 0.0 | PASS |
| rag | warning_retention_rate | 1.0 | 1.0 | 0.0 | PASS |
| rag | case_pass_rate | 1.0 | 1.0 | 0.0 | PASS |
| rag | knowledge_tool_success_rate | 0.611111 | 0.611111 | 0.0 | PASS |
| rag | canonical_excerpt_accuracy | 1.0 | 1.0 | 0.0 | PASS |
| rag | decision_invariance | 1.0 | 1.0 | 0.0 | PASS |
| rag | fallback_success_rate | 1.0 | 1.0 | 0.0 | PASS |
| retrieval | recall_at_4 | 0.786667 | 0.786667 | 0.0 | PASS |
| retrieval | mrr_at_4 | 0.715 | 0.715 | 0.0 | PASS |
| retrieval | ndcg_at_4 | 0.69018 | 0.69018 | 0.0 | PASS |
| retrieval | forbidden_document_rate | 0.05 | 0.05 | 0.0 | PASS |
| retrieval | filter_violation_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | unsupported_fact_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | proposal_rule_violation_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | unauthorized_write_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | rejected_proposal_write_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | duplicate_apply_rate | 0.0 | 0.0 | 0.0 | PASS |
| weekly_adaptive | warning_retention | 1.0 | 1.0 | 0.0 | PASS |
| weekly_adaptive | case_pass_rate | 1.0 | 1.0 | 0.0 | PASS |
| weekly_adaptive | weekly_facts_accuracy | 1.0 | 1.0 | 0.0 | PASS |
| weekly_adaptive | rule_consistency | 1.0 | 1.0 | 0.0 | PASS |
| weekly_adaptive | fallback_success_rate | 1.0 | 1.0 | 0.0 | PASS |
| weekly_adaptive | rollback_success_rate | 1.0 | 1.0 | 0.0 | PASS |

## Failures

| Suite | Case ID | Category |
|---|---|---|
| retrieval | ret_single_001 | RETRIEVAL_FAILURE |
| retrieval | ret_single_007 | RETRIEVAL_FAILURE |
| retrieval | ret_single_011 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_002 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_003 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_004 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_006 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_007 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_008 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_009 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_011 | RETRIEVAL_FAILURE |
| retrieval | ret_multi_012 | RETRIEVAL_FAILURE |
| retrieval | ret_hard_001 | RETRIEVAL_FAILURE |
| retrieval | ret_hard_002 | RETRIEVAL_FAILURE |
| retrieval | ret_hard_004 | RETRIEVAL_FAILURE |
| retrieval | ret_hard_005 | RETRIEVAL_FAILURE |
| retrieval | ret_hard_007 | RETRIEVAL_FAILURE |

## Reproduce

`python scripts/evaluate_agent.py --suite all`
