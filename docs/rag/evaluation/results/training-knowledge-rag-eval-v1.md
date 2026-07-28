# Training Knowledge Rag Evaluation v1

## Scope

- Dataset: `rag-answer-cases-v1`
- Dataset SHA-256: `a00fb766e1fb446055f5150e4b251792112a3b7ea3c5aafdf635557cd5b0a1f7`
- Corpus root: `58bae62329a833c7a2a2a79dc12d31ac8c1b8052144597c839700e4b18894a7b`
- Index: `not used`
- Provider/model: `fake` / `deterministic-fake-v1`
- Execution: offline/fake provider
- Mode: `FULL_SYSTEM`
- Cases: 36
- Raw answers saved: **No**
- Generated at: 2026-07-28T03:51:53.564396+00:00
- Result hash: `d0557fa09d241b8bfb30cb21dae9cb6417d277ef3b51902f03824a934e1330ce`

## Metrics

| Metric | Result |
| --- | ---: |
| canonical_excerpt_accuracy | 1.0000 |
| case_pass_rate | 1.0000 |
| citation_precision | 1.0000 |
| citation_recall | 1.0000 |
| citation_requirement_satisfaction | 1.0000 |
| decision_invariance | 1.0000 |
| fallback_success_rate | 1.0000 |
| forbidden_tool_call_rate | 0.0000 |
| intent_accuracy | 1.0000 |
| knowledge_tool_success_rate | 0.6111 |
| limitation_retention_rate | 1.0000 |
| provider_success_rate | 0.8611 |
| required_tool_recall | 1.0000 |
| rule_violation_rate | 0.0000 |
| source_hallucination_rate | 0.0000 |
| unauthorized_plan_modification_rate | 0.0000 |
| unsupported_claim_rate | 0.0000 |
| warning_retention_rate | 1.0000 |

## Failed cases

None

## Known limitations

- The public RAG evaluation uses fixed fictional contexts and stores no raw answer, prompt, context, tool result, or reasoning content.

## Reproduce

Run `python scripts/evaluate_training_knowledge.py rag` from
the repository root. Real-provider runs require server-side environment settings;
API keys are never command-line arguments or report fields.

## Safety boundary

The report contains case identifiers, ranked chunk/document identifiers, scores,
safe validation codes, and aggregate metrics only. It excludes raw provider
answers, prompts, contexts, tool results, vectors, credentials, and identities.
