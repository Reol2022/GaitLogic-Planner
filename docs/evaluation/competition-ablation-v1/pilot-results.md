# Competition Ablation Pilot Results

- Cases: 10
- Runs per case: 1
- Total model calls: 60
- Provider mode: real
- Provider: openai_compatible
- Model: deepseek-v4-flash
- Thinking: enabled
- Temperature: 0.2
- Max output tokens: 8192

| Variant | Fact Consistency | Supported Decision | Partial Facts Response | False Global Block | Blocked Hallucination | Avg Latency (ms) | Avg Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A_LLM_ONLY | 50.00% | 0.00% | 0.00% | 20.00% | 0.00% | 14219.74 | 2019.10 |
| B_TOOLS_LLM | 75.00% | 0.00% | 0.00% | 20.00% | 0.00% | 17253.01 | 2450.20 |
| C_TRUSTED_CORE | 80.00% | 0.00% | 0.00% | 20.00% | 25.00% | 23080.38 | 3207.30 |
| D_PARTIAL_FACTS | 85.00% | 8.33% | 40.00% | 60.00% | 0.00% | 24335.63 | 3533.00 |
| E_EVIDENCE_JUDGE | 85.00% | 0.00% | 20.00% | 80.00% | 0.00% | 26251.66 | 3294.80 |
| F_FULL_GAITLOGIC | 80.00% | 7.69% | 80.00% | 20.00% | 0.00% | 34781.28 | 3354.30 |

## Fractions

### A_LLM_ONLY

- fact_consistency: 10/20 = 50.00%
- supported_decision: 0/12 = 0.00%
- partial_facts_response: 0/5 = 0.00%
- false_global_block: 1/5 = 20.00%
- blocked_domain_hallucination: 0/4 = 0.00%

### B_TOOLS_LLM

- fact_consistency: 15/20 = 75.00%
- supported_decision: 0/10 = 0.00%
- partial_facts_response: 0/5 = 0.00%
- false_global_block: 1/5 = 20.00%
- blocked_domain_hallucination: 0/4 = 0.00%

### C_TRUSTED_CORE

- fact_consistency: 16/20 = 80.00%
- supported_decision: 0/10 = 0.00%
- partial_facts_response: 0/5 = 0.00%
- false_global_block: 1/5 = 20.00%
- blocked_domain_hallucination: 1/4 = 25.00%

### D_PARTIAL_FACTS

- fact_consistency: 17/20 = 85.00%
- supported_decision: 1/12 = 8.33%
- partial_facts_response: 2/5 = 40.00%
- false_global_block: 3/5 = 60.00%
- blocked_domain_hallucination: 0/4 = 0.00%

### E_EVIDENCE_JUDGE

- fact_consistency: 17/20 = 85.00%
- supported_decision: 0/10 = 0.00%
- partial_facts_response: 1/5 = 20.00%
- false_global_block: 4/5 = 80.00%
- blocked_domain_hallucination: 0/4 = 0.00%

### F_FULL_GAITLOGIC

- fact_consistency: 16/20 = 80.00%
- supported_decision: 1/13 = 7.69%
- partial_facts_response: 4/5 = 80.00%
- false_global_block: 1/5 = 20.00%
- blocked_domain_hallucination: 0/4 = 0.00%

## Provider and Schema Failures

None.

## Limitations

- Fixed public fictional cases are not a longitudinal athlete study.
- Deterministic scoring covers bounded safety and factual contracts, not all language quality.
- Provider outputs are stochastic when the provider does not support a fixed seed.
