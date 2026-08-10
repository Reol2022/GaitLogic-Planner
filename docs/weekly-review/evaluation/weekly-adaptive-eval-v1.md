# GaitLogic v0.13 Weekly/Adaptive Public Evaluation

This deterministic offline evaluation uses only fictional data.

Cases: 32/32

| Metric | Result |
|---|---:|
| Case Pass Rate | 100.00% |
| Weekly Facts Accuracy | 100.00% |
| Rule Consistency | 100.00% |
| Warning Retention | 100.00% |
| Unsupported Fact Rate | 0.00% |
| Proposal Rule Violation Rate | 0.00% |
| Unauthorized Write Rate | 0.00% |
| Rejected Proposal Write Rate | 0.00% |
| Duplicate Apply Rate | 0.00% |
| Rollback Success Rate | 100.00% |
| Fallback Success Rate | 100.00% |

Failed cases: None

## Reproduce

`python scripts/evaluate_weekly_adaptive.py`

## Limits

- Write, idempotency and rollback metrics are backed by the dedicated MySQL integration suite, not by this offline case runner.
- All cases use fixed fictional dates and data; no Provider or production database is accessed.
