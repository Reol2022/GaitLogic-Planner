# Runner State 自动快照触发回执 v1

## 目标与边界

C2.3-B 建立 Garmin 同步后的内部自动快照处理能力，但尚未接入 Pipeline、后台任务、同步 API 或前端。它不触发真实同步、不修改训练计划、不调用大语言模型，也不改变 Runner State 推断、canonical JSON、SHA-256 或现有 payload 去重键。

快照回答“当时的跑者状态是什么”，回执回答“某次同步运行是否已经处理以及结果如何”。两种事实分表保存，避免为了事件幂等而修改不可变历史快照。

## 表结构

`runner_state_snapshot_trigger_receipt` 以 `id` 为主键，包含事件身份（`user_id`、`trigger_type`、`trigger_reference`、`sync_job_id`）、处理状态（`status`、`attempt_count`、`processing_token`、`locked_at`、`completed_at`）、输入摘要（`is_committed`、`material_change_count`）、结果（`snapshot_id`、`error_code`、`safe_error_message`）以及创建更新时间。

外键删除语义分别为用户 `CASCADE`、快照 `SET NULL`、同步 Job `SET NULL`。唯一约束为 `(user_id, trigger_type, trigger_reference)`；普通索引覆盖用户时间、Job、状态租约和快照查询。`material_change_count` 与 `attempt_count` 不能为负。

快照表仍只使用 `(user_id, data_cutoff_date, payload_hash)` 做内容去重，没有增加 trigger reference 唯一约束。

## 触发引用与两层幂等

Garmin 固定使用：

```text
trigger_type = GARMIN_SYNC
trigger_reference = garmin-sync:<canonical sync_run_id UUID>
```

`sync_run_id` 是服务器生成、跨 Job 重试复用的逻辑运行 ID；Job ID 只是一次具体尝试。构造函数拒绝空值、非 UUID、非规范小写 UUID 和超长结果，不接受时间戳或客户端幂等键。

两层幂等分别由回执唯一约束和快照 payload hash 实现。不同同步运行命中同一 payload 时，回执为 `DUPLICATE_PAYLOAD` 并指向旧快照。旧快照可能来自 `MANUAL`，其 trigger 字段不会被覆盖。

## 状态机

数据库状态为 `PROCESSING`、`CREATED`、`DUPLICATE_PAYLOAD`、`SKIPPED_NO_MATERIAL_CHANGE`、`SKIPPED_NOT_COMMITTED` 和 `FAILED_NON_BLOCKING`。

首次领取直接尝试插入 `PROCESSING`，`attempt_count=1`，并设置服务器 UUID token 与租约时间。唯一冲突后才读取已有回执：

- `CREATED` / `DUPLICATE_PAYLOAD` 返回 `ALREADY_PROCESSED_TRIGGER`，不重新计算；
- 未过期 `PROCESSING` 返回 `PROCESSING_BY_ANOTHER_WORKER`；
- 跳过或失败状态可用带旧状态条件的 UPDATE 重新领取；
- 超过 15 分钟的 `PROCESSING` 可用带旧 `locked_at` 条件的 UPDATE 恢复。

领取成功会增加 `attempt_count`、换新 token、更新最新 Job 和同步结果，并清空旧错误。跳过状态必须可重新打开，因为同一逻辑同步的第一次 Job 可能未提交，后续重试仍可能成功。

## 租约与 processing token

15 分钟租约集中定义为 `RUNNER_STATE_RECEIPT_LEASE`。过期恢复只有条件 UPDATE 的 `rowcount == 1` 才获得处理权。完成回执同时校验 `receipt_id + PROCESSING + processing_token`，因此旧 Worker 不能覆盖新 Worker 的结果。完成后 token 被清空，`locked_at` 保留最后一次领取时间。

## 输入与快照事务

- `committed=false`：`SKIPPED_NOT_COMMITTED`，不计算或保存；
- 已提交但变化数为 0：`SKIPPED_NO_MATERIAL_CHANGE`，不计算或保存；
- 变化数小于 0：拒绝非法内部输入；
- 已提交且变化数大于 0：进入快照事务。

服务校验 Job、用户和 sync run 归属。处理分为事务 A（领取并提交 `PROCESSING`）和事务 B（验证 token、计算当前状态、创建或复用快照、条件完成回执并统一提交）。

`RunnerStateSnapshotService.create_or_get_snapshot_in_transaction` 只 `flush()`，不最终 `commit()`；手动保存仍由原服务外层提交，API 响应不变。自动新快照使用 `GARMIN_SYNC`，重复 payload 只复用旧记录。

## 失败隔离

阶段 B 的状态计算、序列化、持久化、回执完成或提交失败时先 rollback，再在干净事务中仅由当前 token 持有者写入 `FAILED_NON_BLOCKING`。错误只返回固定安全码；日志不包含完整 payload、Evidence、Token、身份字段、SQL 或凭据。自动快照失败不会修改 `ExternalSyncJob` 或 Garmin Outcome。

## 迁移、重试与当前限制

`scripts/upgrade_v0103_runner_state_snapshot_receipts.py` 只创建或删除回执表，重复执行明确失败；不回填旧 Job、不扫描训练数据、不修改快照或同步表。失败和跳过回执可由相同 sync run 的后续 Job 重新领取，终态则直接复用结果。

C2.3-B 尚未在 Garmin Pipeline、BackgroundTask、Worker 或路由中调用服务，也没有同步结果字段、前端提示、DAILY/PLAN_ADJUSTMENT/SYSTEM 触发或真实自动快照。C2.3-C 才负责 commit 后接入。
