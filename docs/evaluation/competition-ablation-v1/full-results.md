# Competition Ablation Full Results

- Cases: 24
- Runs per case: 3
- Total model calls: 432
- Provider mode: real
- Provider: openai_compatible
- Model: deepseek-v4-flash
- Thinking: enabled
- Temperature: 0.2
- Max output tokens: 8192

| Variant | Fact Consistency | Supported Decision | Partial Facts Response | False Global Block | Blocked Hallucination | Avg Latency (ms) | Avg Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_LLM_ONLY | 81.16% | 2.17% | 10.26% | 25.64% | 3.70% | 21008.21 | 2797.01 |
| B_TOOLS_LLM | 89.86% | 2.20% | 5.13% | 25.64% | 3.70% | 23192.80 | 3122.83 |
| C_TRUSTED_CORE | 75.36% | 0.00% | 10.26% | 20.51% | 7.41% | 22092.12 | 2973.74 |
| D_PARTIAL_FACTS | 88.41% | 20.00% | 41.03% | 56.41% | 0.00% | 23524.68 | 3266.53 |
| E_EVIDENCE_JUDGE | 93.48% | 12.86% | 41.03% | 58.97% | 0.00% | 25449.96 | 3221.47 |
| F_FULL_GAITLOGIC | 96.38% | 12.82% | 58.97% | 41.03% | 0.00% | 19757.18 | 2807.92 |

## Fractions

### A_LLM_ONLY

- fact_consistency: 112/138 = 81.16%
- supported_decision: 2/92 = 2.17%
- partial_facts_response: 4/39 = 10.26%
- false_global_block: 10/39 = 25.64%
- blocked_domain_hallucination: 1/27 = 3.70%

### B_TOOLS_LLM

- fact_consistency: 124/138 = 89.86%
- supported_decision: 2/91 = 2.20%
- partial_facts_response: 2/39 = 5.13%
- false_global_block: 10/39 = 25.64%
- blocked_domain_hallucination: 1/27 = 3.70%

### C_TRUSTED_CORE

- fact_consistency: 104/138 = 75.36%
- supported_decision: 0/77 = 0.00%
- partial_facts_response: 4/39 = 10.26%
- false_global_block: 8/39 = 20.51%
- blocked_domain_hallucination: 2/27 = 7.41%

### D_PARTIAL_FACTS

- fact_consistency: 122/138 = 88.41%
- supported_decision: 14/70 = 20.00%
- partial_facts_response: 16/39 = 41.03%
- false_global_block: 22/39 = 56.41%
- blocked_domain_hallucination: 0/27 = 0.00%

### E_EVIDENCE_JUDGE

- fact_consistency: 129/138 = 93.48%
- supported_decision: 9/70 = 12.86%
- partial_facts_response: 16/39 = 41.03%
- false_global_block: 23/39 = 58.97%
- blocked_domain_hallucination: 0/27 = 0.00%

### F_FULL_GAITLOGIC

- fact_consistency: 133/138 = 96.38%
- supported_decision: 10/78 = 12.82%
- partial_facts_response: 23/39 = 58.97%
- false_global_block: 16/39 = 41.03%
- blocked_domain_hallucination: 0/27 = 0.00%

## Provider and Schema Failures

None.

## Limitations

- Fixed public fictional cases are not a longitudinal athlete study.
- Deterministic scoring covers bounded safety and factual contracts, not all language quality.
- Provider outputs are stochastic when the provider does not support a fixed seed.
