# Garmin 同步事务与 Material Change 契约 v1

## 目标与范围

v0.10.3-C2.3-A 让 Garmin 同步明确回答三件事：哪一次逻辑同步正在执行、训练事实是否已经提交、这次提交是否改变 Runner State 的输入。本阶段只建设同步基础设施，不创建 Runner State 自动快照，也不调用快照服务。

## 同步入口与统一 Pipeline

手动 Garmin 接口和通用 Data Sync 接口创建 `ExternalSyncJob` 后，由 FastAPI `BackgroundTasks` 调用 `ActivitySyncPipeline.run_job()`。轮询 Worker 使用同一 Pipeline 的 `run_next_job()`，不再直接调用 Garmin 业务服务。

两类执行器最终使用同一个链路：

```text
BackgroundTask / polling Worker
  -> ActivitySyncPipeline
  -> atomic claim
  -> garmin_sync_service.run_sync_job
  -> GarminSyncRunOutcome
```

两个 retry 接口保持原产品行为：只创建 queued Job，等待 Worker 领取，不在路由中启动另一套立即执行逻辑。

## 原子领取

任务领取使用条件更新：

```sql
UPDATE external_sync_job
SET status = 'running', attempt_count = attempt_count + 1, ...
WHERE id = :job_id AND status = 'queued';
```

只有受影响行数为 1 的执行者获得执行权。第二个执行者得到 `claimed=false` 和 `JOB_NOT_CLAIMED`，不会解密令牌、创建 Provider 或拉取活动。`running` Job 不再被接受为可执行 Job。

## sync_run_id 与重试

`sync_run_id` 是服务端生成的 UUID 字符串，长度为 36。首次创建逻辑同步时生成；客户端请求 Schema 不包含该字段。重试仍创建新的 Job ID，但继承原 Job 的 `sync_run_id`、同步模式与时间范围，并重置运行时间和所有计数。

因此：

- Job ID 标识一次具体尝试；
- `sync_run_id` 标识跨重试的同一次逻辑同步；
- 客户端 `Idempotency-Key` 继续服务于入队幂等，不充当内部运行标识；
- `sync_run_id` 只有普通索引，没有唯一约束。

## 主事务边界

领取 Job 的状态提交与训练数据主事务分开。领取成功后，ExternalActivity、关联表、WorkoutLog、复合活动汇总和同步结果字段在主事务中处理。

- 正常完成：设置 `is_committed=true`、`committed_at` 和最终计数，与训练事实一起 commit；
- 无活动：状态为 `succeeded`，仍表示一次成功提交，material change 为 0；
- 部分活动失败：每条活动使用保存点，至少一条成功时提交成功部分，状态为 `partially_succeeded`；
- 全部活动失败：rollback 整个训练事务，再用干净事务标记 Job 为 `failed`；
- Provider、解密、刷新等致命异常：先 rollback，再标记失败；
- 最终 commit 失败：先 rollback，随后在恢复后的干净事务中标记失败。

失败标记事务不会携带 ExternalActivity、WorkoutLog、关联或复合汇总数据。`committed_at` 只在主事务真正提交时存在。

## Material Change 投影

`RunnerStateRelevantWorkoutLogProjection` 只包含 Runner State A/B 实际读取、且 Garmin 同步可能改变的 WorkoutLog 字段：

| 字段 | 语义 |
| --- | --- |
| `planned_workout_id` | 计划关联及完成率归属 |
| `activity_date` | 7/28 天窗口归属 |
| `status_normalized` | 完成、休息和有效训练判定 |
| `workout_type` | 强度、关键课和长距离分类输入 |
| `actual_distance_km` | 距离指标 |
| `actual_duration_seconds` | 时长指标 |
| `rpe` | RPE 均值与覆盖率 |
| `avg_heart_rate` | 心率覆盖率 |
| `max_heart_rate` | 心率覆盖率 |

Decimal、float、枚举、日期和 null 在投影中规范化。比较不依赖 `updated_at`、payload hash 或 SQLAlchemy dirty 状态。配速、步频、海拔、热量、Garmin Training Effect、抓取时间和原始 payload 不进入投影。

每个活动使用局部 Tracker；保存点成功后才合并到整次同步 Tracker。第一次触碰既有日志时保存 before，全部活动与复合汇总结束后读取 final after。同一 WorkoutLog 被多段活动更新只统计一次。保存点或主事务回滚的新增日志不会进入已提交计数。

## 持久化计数

`ExternalSyncJob` 新增：

- `created_log_count`
- `updated_log_count`
- `unchanged_activity_count`
- `runner_state_affecting_change_count`
- `is_committed`
- `committed_at`

当前同步流程不删除或失效 WorkoutLog，因此：

```text
runner_state_affecting_change_count
  = created_log_count + updated_log_count
```

原有 `created_count`、`updated_count`、`duplicate_count` 等 ExternalActivity 计数保持原语义，没有被替换。

## GarminSyncRunOutcome

内部 Outcome 包含：

```json
{
  "job_id": 1201,
  "sync_run_id": "8ded13f6-bdaa-4417-b386-9f32b3bc35dd",
  "claimed": true,
  "committed": true,
  "final_status": "partially_succeeded",
  "created_log_count": 1,
  "updated_log_count": 1,
  "unchanged_activity_count": 2,
  "runner_state_affecting_change_count": 2,
  "warning_codes": ["ACTIVITY_PROCESSING_PARTIAL_FAILURE"]
}
```

示例完全虚构。Outcome 不含 Token、原始活动 JSON、完整训练日志、Evidence 或异常堆栈。

## 数据库升级

`scripts/upgrade_v0103_garmin_sync_material_change.py` 是独立升级脚本：

1. 增加可空 `sync_run_id` 和结果字段；
2. 由 Python 服务端 UUID 为每条历史 Job 独立回填；
3. 检查没有 NULL；
4. 改为 NOT NULL 并建立普通索引。

downgrade 删除索引和全部新增字段。脚本只支持隔离 MySQL，避免 SQLite 被误当作产品数据库；SQL 不使用 MySQL 8 专属的 `ADD COLUMN IF NOT EXISTS` 或时间戳幂等键，兼容 MySQL 5.7 语法。本地验证必须在临时测试库执行，不能对生产库试跑。

## API 兼容性

既有同步 Job 响应增加只读字段。前端 TypeScript 将它们声明为可选，以兼容滚动发布期间的旧后端；本阶段不新增展示，也不改变同步按钮行为。

## 当前限制与 C2.3-B 边界

- 尚未创建 `GARMIN_SYNC` Runner State 快照；
- 尚未调用 `RunnerStateSnapshotService`；
- 尚未增加快照 trigger reference 唯一约束；
- 尚未实现快照失败隔离或前端提示；
- 手工 reconcile/resolve 不是 Job 同步 Outcome 的组成部分；
- 若未来同步增加日志删除或失效路径，必须扩展 material change 计数公式和测试。

C2.3-B 才能消费 `GarminSyncRunOutcome`，在已提交且 material change 大于 0 时编排自动快照。

