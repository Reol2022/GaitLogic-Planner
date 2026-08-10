# v0.13 Source Code Map

| 功能 | 文件 | 核心类/函数 | 输入 | 输出 | 调用方 |
|---|---|---|---|---|---|
| 周事实 Schema | `planner_core/weekly_review/schemas.py` | `WeeklyFactsRequest`, `WeeklyFacts` | 周窗口与领域 Fact | 严格周事实 | 聚合、API、Graph |
| 周事实聚合 | `planner_core/weekly_review/aggregation.py` | `build_weekly_facts()` | Plan、Log、Runner State | `WeeklyFacts` | `WeeklyFactsService` |
| ORM 查询适配 | `server/services/weekly_facts_service.py` | `WeeklyFactsService.build_weekly_facts()` | Session、当前用户请求 | `WeeklyFacts` | Weekly API |
| 周复盘 State | `server/weekly_review_graph/schemas.py` | `WeeklyReviewState`, `WeeklyReviewResult` | facts/rules/references | 公共复盘 | Graph/API |
| 周复盘节点 | `server/weekly_review_graph/nodes.py` | `WeeklyReviewNodes` | `WeeklyReviewState` | State patch | LangGraph |
| 周复盘图 | `server/weekly_review_graph/workflow.py` | `build_weekly_review_graph()` | ports、tracer | compiled graph | Weekly API/tests |
| Provider/RAG 适配 | `server/weekly_review_graph/adapters.py` | `AgentGatewayWeeklyReviewGenerator`, `KnowledgeToolWeeklyRetriever` | Gateway/Tool | draft/retrieval | Weekly API |
| Proposal Schema | `planner_core/adaptive_plan/schemas.py` | `PlanAdjustmentProposal` | candidate changes | 严格 Diff | Proposal Service/UI |
| Proposal 规则 | `server/services/adaptive_plan_proposal_service.py` | `AdaptivePlanProposalService.create_proposal()` | facts、targets、candidates | 无副作用 Proposal | 应用层/tests |
| 审批写入 | `server/services/adaptive_plan_approval_service.py` | `persist_proposal()`, `approve()`, `reject()` | 当前用户、proposal | 状态/版本 | Adaptive API |
| 版本与回滚 | `server/services/adaptive_plan_version_service.py` | `list_versions()`, `rollback()` | 用户、版本 | 版本记录 | Adaptive API |
| 审批图 | `server/adaptive_workflow/graph.py` | `request_human_approval()`, `build_adaptive_approval_graph()` | proposal state | interrupt/resume | HITL service/tests |
| 持久 Checkpoint | `server/adaptive_workflow/checkpointer.py` | `SQLAlchemyCheckpointSaver` | LangGraph config/checkpoint | DB checkpoint | approval graph |
| ORM | `planner_core/database/models.py` | `AdaptivePlanVersionRecord`, `AdaptiveWorkflowCheckpointRecord`, `AdaptiveWorkflowCheckpointWriteRecord` | SQLAlchemy values | MySQL rows | services/saver |
| 迁移 | `scripts/upgrade_v0130_adaptive_plan.py` | upgrade/downgrade entry | DB connection | v0.13 tables | deployment |
| API | `server/api/routes/weekly_reviews.py` | facts/graph/proposal/approve/reject/version/rollback routes | JWT current user | safe schemas | Vue client |
| Trace | `server/observability/tracing.py` | `SafeTracer`, `SpanRecord` | safe attributes | spans | Graph/approval |
| 前端 API | `web/src/api/adaptivePlan.ts` | request helpers | dates/proposal id | typed DTO | Adaptive view |
| 周事实 UI | `web/src/components/weekly-review/WeeklyFactsPanel.vue` | component | WeeklyFacts | facts cards | Adaptive view |
| Proposal Diff UI | `web/src/components/weekly-review/AdaptiveProposalDiff.vue` | component | Proposal | before/after/actions | Adaptive view |
| 页面 | `web/src/views/AdaptiveWeeklyReviewView.vue` | view | current route/user actions | full review experience | Router |
| 公开评测 | `server/weekly_review_evaluation.py` | `load_cases()`, `run_evaluation()` | fictional JSONL | metrics/report | eval CLI |
| 评测 CLI | `scripts/evaluate_weekly_adaptive.py` | `main()` | public cases | JSON/Markdown | developer/CI |

## 快速定位顺序

事实算错：先看 `aggregation.py`，再看 `WeeklyFactsService` 的 ORM 映射。图走错分支：看 `workflow.py::_after_validation` 和 `nodes.py` 的状态变更。Proposal 被拒：看 `_validate_change` 与 `_validate_resulting_week`。批准重复或回滚异常：看 approval/version service 与 MySQL integration tests。页面字段错：先核对 `web/src/types/adaptivePlan.ts` 与 OpenAPI Schema，再看 API client 和组件。
