# Release gate

## Feature gates

| Gate | Result | Evidence |
|---|---|---|
| Coach | PASS | 32/32 public fictional evaluation cases |
| RAG | PASS | 36/36; source hallucination and unauthorized modification rates are zero |
| Weekly | PASS | 32/32 Weekly Adaptive cases |
| Plan Design | PASS | Independent real Provider smoke and structured schema tests |
| Partial Facts | PASS | Domain readiness and proposal-safety regression tests |
| Evidence Reflect | PASS | 10/10; duplicate/unsupported/infinite-loop rates are zero |
| Proposal Safety | PASS | BLOCKED recovery increase rejected before apply |
| MCP | PASS | 45/45 read-only and identity-boundary cases |
| Frontend | PASS | typecheck, 135 tests, production build |

## Environment and evaluation gates

| Gate | Result | Notes |
|---|---|---|
| Retrieval v1 | HISTORICAL PASS | Frozen 12-document manifest reproduces 43/60 and all historical baseline deltas are zero. |
| Retrieval v2 | PASS WITH KNOWN IMPROVEMENT CASES | Audited 52-document fixture: 52/60 Dense, all versioned baseline gates pass, forbidden/filter rates are zero. |
| BM25 / Hybrid v2 | PASS WITH FINDINGS | 48/60 and 52/60 respectively; Hybrid has 0.05 forbidden-document rate requiring future retrieval work. |
| Real reranker v2 | NOT_RUN | Provider is disabled or incomplete; deterministic fallback remains available. |
| MySQL 8 runtime | BLOCKED_ENVIRONMENT | Server 8.0.45 is reachable, but `gaitlogic_test` does not exist and the application account cannot create it. |
| MySQL 5.7 runtime | NOT_RUN | No runtime is installed; this alone is not a release blocker. |
| MySQL 5.7 static compatibility | PASS | Existing migration/index syntax tests pass. |
| Build | PASS | Python wheel/sdist and frontend production build succeed. |
| OpenAPI / MCP | PASS | Version endpoint contract and MCP suites pass. |
| Security | PASS | Changed-file scan found no literal secret; public reports contain no raw reasoning. |
| Release version | PASS | Formal backend, frontend, OpenAPI, README, change history and release notes use 0.16.3; v0.16.0 notes remain historical. |

The code is ready for logical staging review as v0.16.3. If release policy requires live MySQL integration before publication, an administrator must first create the isolated test database.
