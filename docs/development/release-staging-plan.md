# Release staging plan

This plan describes future manual staging only. It must be executed from the canonical workspace after reviewing every hunk. It does not use `git add .` or `git add -A`.

The current diff contains no unstaged Garmin, Hybrid RAG corpus, Partial Facts, or core DeepSeek Task Profile implementation files; those capabilities are already present in HEAD. Do not manufacture empty commits for Groups 1–5.

## Commit 1 — Evidence Judge and bounded Reflect

Suggested message: `feat: add evidence-driven reflect loop`

```powershell
git add .env.example
git add planner_core/config.py
git add server/domain/evidence.py
git add server/evidence_evaluation.py
git add server/services/evidence_judge_service.py
git add server/services/evidence_reflect_service.py
git add server/agent/orchestrator.py
git add server/agent/prompts.py
git add server/agent/schemas.py
git add server/agent/tool.py
git add server/agent/tools/knowledge_tools.py
git add server/agent/tools/planning_tools.py
git add server/agent/tools/rule_tools.py
git add server/agent/tools/runner_state_tools.py
git add server/agent/tools/training_tools.py
git add server/agent/training_context_builder.py
git add server/agent/validator.py
git add server/observability/metrics.py
git add server/observability/tracing.py
git add server/weekly_review_graph/adapters.py
git add server/weekly_review_graph/nodes.py
git add server/weekly_review_graph/ports.py
git add server/weekly_review_graph/schemas.py
git add server/weekly_review_graph/workflow.py
git add tests/test_evidence_coach_integration.py
git add tests/test_evidence_judge.py
git add tests/test_evidence_reflect.py
git add tests/test_evidence_validator.py
git add tests/test_agent_metrics.py
git add tests/test_agent_workflow_tracing.py
git add tests/test_weekly_review_graph.py
git add scripts/smoke_evidence_reflect.py
```

Shared-file hunks to stage interactively:

```powershell
git add -p scripts/evaluate_agent.py
git add -p server/agent/evaluation_regression/gates.py
git add -p server/agent/evaluation_regression/registry.py
git add -p server/api/routes/weekly_reviews.py
git add -p tests/test_agent_evaluation_regression.py
```

Select only Evidence/Reflect imports, suite registration, graph wiring and related tests. Leave Retrieval v2 and Approval hunks unstaged.

Verification: `pytest -q tests/test_evidence_judge.py tests/test_evidence_reflect.py tests/test_evidence_coach_integration.py tests/test_evidence_validator.py tests/test_weekly_review_graph.py tests/test_agent_metrics.py`

## Commit 2 — Adaptive approval and proposal safety

Suggested message: `feat: harden adaptive proposal approval`

```powershell
git add server/adaptive_workflow/graph.py
git add server/services/approval_workflow_service.py
git add server/services/adaptive_plan_proposal_service.py
git add server/services/coach_agent_query_service.py
git add server/services/plan_adjustment_apply_service.py
git add server/services/plan_adjustment_validation_service.py
git add server/services/weekly_review_ai_service.py
git add tests/test_adaptive_approval_graph.py
git add tests/test_adaptive_plan_hitl.py
git add tests/test_adaptive_plan_proposal_service.py
git add tests/test_weekly_review_stats.py
git add web/src/views/MyView.vue
git add web/src/views/MyView.test.ts
git add -p server/api/routes/weekly_reviews.py
```

Select only pending checkpoint creation, approve/reject routing, ownership, proposal validation and hidden experimental-entry hunks.

Verification: `pytest -q tests/test_adaptive_approval_graph.py tests/test_adaptive_plan_hitl.py tests/test_adaptive_plan_proposal_service.py tests/test_weekly_review_stats.py`

## Commit 3 — Runtime and workspace diagnostics

Suggested message: `chore: consolidate runtime and workspace diagnostics`

```powershell
git add scripts/start_backend.ps1
git add server/api/routes/health.py
git add server/common/response.py
git add tests/test_api_structure.py
git add docs/development/worktree-policy.md
git add docs/development/legacy-worktree-audit.md
git add docs/development/mysql-integration-setup.md
```

Verification: `pytest -q tests/test_api_structure.py tests/test_public_boundary_check.py`

## Commit 4 — Versioned expanded-corpus Retrieval evaluation

Suggested message: `test: version retrieval evaluation for expanded corpus`

```powershell
git add docs/evaluation/baselines/agent-regression-v1.json
git add docs/evaluation/baselines/retrieval-v1-corpus-manifest.json
git add docs/evaluation/retrieval-evaluation-v2-semantic-audit.md
git add docs/evaluation/retrieval-unified-workspace-investigation-v1.md
git add docs/evaluation/reports/retrieval-hybrid-comparison-v2.json
git add docs/evaluation/reports/retrieval-hybrid-comparison-v2.md
git add docs/evaluation/reports/retrieval-reranker-comparison-v2.json
git add docs/evaluation/reports/retrieval-reranker-comparison-v2.md
git add docs/rag/evaluation/cases/retrieval-eval-v2.json
git add scripts/build_retrieval_eval_v2.py
git add scripts/evaluate_hybrid_retrieval.py
git add scripts/evaluate_reranker.py
git add server/knowledge_retrieval/evaluation/datasets.py
git add server/knowledge_retrieval/evaluation/retrieval_metrics.py
git add server/knowledge_retrieval/evaluation/runner.py
git add server/knowledge_retrieval/evaluation/schemas.py
git add tests/test_training_knowledge_evaluation_datasets.py
git add tests/test_training_knowledge_retrieval_metrics.py
git add -p scripts/evaluate_agent.py
git add -p server/agent/evaluation_regression/gates.py
git add -p server/agent/evaluation_regression/registry.py
git add -p tests/test_agent_evaluation_regression.py
```

Select only `retrieval_v1`/`retrieval_v2`, version metadata, audited fixture and gate hunks.

Verification: `pytest -q tests/test_training_knowledge_evaluation_datasets.py tests/test_training_knowledge_retrieval_metrics.py tests/test_agent_evaluation_regression.py`

## Commit 5 — Version and release documentation

Suggested message: `chore: prepare v0.16.3 release`

```powershell
git add docs/learning/evidence-reflect/00-overview.md
git add docs/learning/evidence-reflect/01-evidence-model.md
git add docs/learning/evidence-reflect/02-evidence-judge.md
git add docs/learning/evidence-reflect/03-conflict-detection.md
git add docs/learning/evidence-reflect/04-decision-relevance.md
git add docs/learning/evidence-reflect/05-reflect-loop.md
git add docs/learning/evidence-reflect/06-tool-capability-mapping.md
git add docs/learning/evidence-reflect/07-coach-integration.md
git add docs/learning/evidence-reflect/08-weekly-integration.md
git add docs/learning/evidence-reflect/09-validator-safety.md
git add docs/learning/evidence-reflect/10-evaluation.md
git add docs/learning/evidence-reflect/11-interview-guide.md
git add docs/learning/evidence-reflect/12-source-code-map.md
git add docs/learning/v0.16.3/01-deepseek-thinking-weekly-planning.md
git add pyproject.toml
git add server/main.py
git add server/api/routes/health.py
git add tests/test_api_structure.py
git add tests/test_release_version_consistency.py
git add web/package.json
git add web/package-lock.json
git add README.md
git add README-EN.md
git add docs/更新历史.md
git add docs/release/v0.16.3.md
git add docs/release/release-gate.md
git add docs/development/release-staging-plan.md
```

Version target is resolved as `0.16.3`. Preserve `docs/release/v0.16.0.md` as historical release evidence.
Do not stage `var/`: it contains generated local evaluation reports and release artifacts, including the 0.16.3 wheel and sdist used for verification.

## Dependency order

1. Evidence domain and Reflect loop.
2. Approval safety, which consumes Weekly/Proposal state.
3. Runtime diagnostics, independent of business behavior.
4. Retrieval evaluation versioning, dependent on the existing expanded corpus.
5. Version and documentation after the four behavior/evaluation groups.

If interactive hunk separation cannot leave `server/api/routes/weekly_reviews.py`, evaluator registry/gates, and their tests compiling after each commit, merge the affected Evidence/Approval commits or Evidence/Retrieval-test commits. Do not create a knowingly broken intermediate commit merely to preserve this suggested count.
