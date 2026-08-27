# Source Code Map

- `server/domain/evidence.py`：canonical schema、assessment、ReflectAction。
- `server/services/evidence_judge_service.py`：profile、materialization、dedupe、conflict、assessment、claim guard。
- `server/services/evidence_reflect_service.py`：capability-aware plan、fingerprint、bounded execution。
- `server/agent/tool.py` 与 `server/agent/schemas.py`：Tool capability 和 request-local context。
- `server/agent/orchestrator.py`：Coach judge/reflect/rejudge integration。
- `server/agent/validator.py`：blocked/conflicted/partial overclaim guard。
- `server/weekly_review_graph/nodes.py` 与 `workflow.py`：Weekly nodes and order。
- `server/weekly_review_graph/adapters.py`：Tool Registry reacquisition 和 Provider context。
- `server/services/adaptive_plan_proposal_service.py`：Proposal recovery safety gate。
- `server/observability/tracing.py` 与 `metrics.py`：privacy-safe spans/metrics。
- `server/evidence_evaluation.py`：公开虚构 Evidence/Reflect suite。
- `tests/test_evidence_*.py`：专项单测和集成测试。
