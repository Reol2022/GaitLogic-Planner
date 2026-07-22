# Architecture relationship

The public product repository contains the running frontend and backend, reusable runner-state and training-knowledge data structures, generic rule-engine and plan-validation frameworks, dynamic-adjustment framework, agent-tool interfaces, anonymous fixtures, and public API documentation.

The private competition repository contains only competition-specific work products and references a product commit through a manifest. It must not copy the product source tree. No competition-specific business implementation is implied by this document.

Runner State Model v1 is a public product capability. It calculates an on-demand,
non-persistent snapshot from the authenticated runner's canonical training plan
and workout-log records. Garmin and other provider activities enter the model
only after the existing normalization, resolution, and workout-log merge flow;
competition data and competition-specific thresholds are not part of this layer.

Runner State Inference v1 is also a public product capability layered on the
Foundation snapshot. It adds versioned, validated heuristic configuration,
an independent previous-21-day baseline, deterministic volume trend,
consistency and fatigue-signal inference, and traceable Evidence/Reason Codes.
It does not infer fitness, modify plans, persist snapshots, or call a language
model. Real-user evaluation, competition experiments, private tuning parameters,
survey responses and presentation materials remain exclusively in the private
competition repository.

Runner State Presentation v1 is the public product display layer for the
on-demand current snapshot. It maps the existing authenticated current-state
GET response into human-readable status cards, deterministic summary copy,
traceable Evidence, data-quality details and responsive layouts. Refreshing the
page does not save a snapshot or write to the database. Historical snapshots,
real-user screenshots, private demonstrations, interview findings and
competition evaluation results are outside this public presentation layer.

Runner State History v1 is the public product persistence layer for immutable,
user-owned state snapshots. C2.1 reuses the existing current-state calculation,
stores a versioned canonical JSON payload, deduplicates identical manual saves
with a stable SHA-256 hash and database uniqueness constraint, and exposes only
authenticated list/detail access. The current-state GET remains read-only.
Automatic device or scheduled triggers, historical trend presentation, real
user histories, competition experiments and private demonstrations are not part
of this public backend foundation.

Runner State History Presentation v1 is the public product read layer over those
immutable snapshots. C2.2 adds an authenticated, server-dated timeline query,
deterministic summaries, volume and categorical-state history, saved risk and
data-quality views, the complete same-day record list, and read-only historical
detail presentation. It neither recalculates historical states nor changes
snapshot persistence, inference rules, Garmin synchronization, or training
plans. Real histories, private screenshots, user research, competition metrics,
and demonstration accounts remain outside the public repository.

Garmin Sync Material Change v1 is the public ingestion contract that precedes
automatic state snapshots. Background execution and the polling worker share
one atomically claimed pipeline; server-generated run IDs survive retries;
transaction outcomes distinguish committed, partial and failed runs; and a
typed WorkoutLog projection reports only changes relevant to Runner State.
This layer does not create snapshots, call the snapshot service, alter state
inference rules, or include real device activity, credentials or competition
results. Automatic snapshot orchestration remains a later product stage.

Runner State Snapshot Trigger Receipts v1 are the public product's internal
event-processing foundation for future automatic snapshots. A dedicated receipt
table separates sync-run idempotency from immutable snapshot content, while a
15-minute processing lease, server token, conditional completion and payload
hash reuse protect concurrent and retried work. Snapshot creation and receipt
completion share one transaction; failures are recorded as non-blocking without
changing Garmin sync results. C2.3-B does not call this service from the
Pipeline, expose a public automatic-snapshot API, include real receipts or
training data, or add competition-specific behavior.

## Garmin 同步后的可解释状态闭环（v0.10.3-C2.3-C）

公开产品能力在统一 Activity Sync Pipeline 完成训练数据事务后，以独立数据库会话触发 Runner
State 自动快照。同步事务与快照事务相互隔离：状态历史失败不会回滚已提交训练数据，也不会改变
同步任务终态。触发回执作为单一事实来源提供幂等状态，任务详情按当前用户只读装配，任务列表
使用批量查询避免 N+1。前端把自动快照显示为同步结果的次级、可解释反馈，GARMIN_SYNC 快照
继续复用既有历史 Timeline 和详情能力。

公开仓库只包含编排、事务隔离、回执投影、界面状态和虚构测试；真实同步任务、用户状态变化、
内测统计和竞赛实验数据仍保留在私有工作区。
