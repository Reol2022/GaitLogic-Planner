# Runner State Garmin Pipeline Integration v1

## 目标与边界

本能力把 Garmin 同步产生的训练事实接入 Runner State 自动快照闭环。唯一接入点是
`ActivitySyncPipeline.run_job`。它不改变 Garmin 拉取、活动去重、训练日志匹配、状态推断、
快照规范化或 SHA-256 去重规则，也不触发训练计划调整。

本版只支持 Garmin 已领取同步任务。reconcile、resolve、restore、reprocess、每日任务和其他
Provider 不触发自动快照。

## Pipeline 唯一接入点

同步顺序固定为：

1. Pipeline 从服务端任务记录确认 Provider；
2. Garmin 同步在 Session A 中原子领取任务并运行；
3. 同步服务提交或回滚训练数据并返回 `GarminSyncRunOutcome`；
4. 只有 `claimed=true` 的 Garmin Outcome 进入后置处理；
5. Pipeline 创建 Session B；
6. `RunnerStateAutoSnapshotService` 根据真实 `committed` 和
   `runner_state_affecting_change_count` 处理回执与快照；
7. Session B 关闭；
8. Pipeline 返回组合结果。

路由、BackgroundTask、轮询 Worker 和单活动处理函数均不得再次调用自动快照服务。

## Session A 与 Session B

Session A 归 Garmin 同步所有，负责活动、日志、关联和同步任务终态。Session B 在 Session A
完成提交后才创建，只负责触发回执、Runner State 计算和历史快照。两个 Session 不共享事务。

Session B 发生异常时会回滚并在 `finally` 中关闭；它不能回滚 Session A，也不能修改同步任务
终态。这样即使状态历史暂时不可用，已经成功提交的训练数据仍保持成功。

## ActivitySyncPipelineResult

Pipeline 返回：

```python
ActivitySyncPipelineResult(
    sync_outcome=GarminSyncRunOutcome(...),
    runner_state_snapshot=RunnerStateAutoSnapshotResult(...) | None,
)
```

`sync_outcome` 保留 Garmin 同步的真实结果。`runner_state_snapshot` 只表示后置处理结果；未领取、
非 Garmin 或尚未进入后置处理时为 `None`。

可信用户身份来自内部 Outcome 的 `user_id`，它由服务端 `ExternalSyncJob.user_id` 生成。客户端
不能提交或覆盖 user_id、sync_run_id、触发类型和 material change 数量。

## 调用条件和状态

- `claimed=false`：不创建 Session B，不查询回执，不计算状态，结果为 `None`；
- Garmin 且已领取：把 Outcome 原值交给自动服务，不在 Pipeline 重复解释业务状态；
- 非 Garmin：当前通用 Pipeline 保持原有“不支持”行为，也不会触发自动快照；
- `committed=false`：由自动服务产生 `SKIPPED_NOT_COMMITTED`；
- material change 为 0：由自动服务产生 `SKIPPED_NO_MATERIAL_CHANGE`；
- 相同 payload：`DUPLICATE_PAYLOAD`，不会新增历史记录；
- 快照创建成功：`CREATED`。

## 自动快照失败隔离

自动服务负责把可预期失败转为 `FAILED_NON_BLOCKING` 并记录安全错误码。Pipeline 还提供最后一层
保护：Session 工厂、服务构造或服务边界抛出意外异常时，回滚并关闭 Session B，记录异常类型
和稳定错误码 `AUTO_SNAPSHOT_PIPELINE_FAILED`，但不记录 Token、原始活动、状态 payload、
Evidence 或数据库凭据，也不重新执行 Garmin Provider。

## 回执查询服务

`RunnerStateSnapshotReceiptQueryService` 是只读投影层。单条查询使用当前用户和
`garmin-sync:<sync_run_id>`；批量查询使用当前用户、`GARMIN_SYNC` 和一组 trigger reference。

只返回：

```json
{
  "status": "CREATED",
  "snapshot_id": 123,
  "error_code": null
}
```

不返回 receipt id、user id、trigger reference、processing token、锁时间、尝试次数、内部安全
消息、material change 数量或快照 payload。查询不会创建回执、计算 Runner State 或写数据库。

## API 嵌套字段与批量装配

`ExternalSyncJobRead` 新增向后兼容可选字段：

```json
{
  "runner_state_snapshot": {
    "status": "CREATED",
    "snapshot_id": 123,
    "error_code": null
  }
}
```

Garmin 和通用 Data Sync 的创建、详情、列表与 retry 使用同一装配语义。详情查询一次回执；列表
先收集当前页所有 Garmin `sync_run_id`，一次查询后按 ID 映射，避免 N+1。queued 任务和上线前
旧任务通常返回 `null`。

## Retry 语义

同一逻辑同步的初始 Job 和 retry Job 共享 `sync_run_id`，因此会读取同一条触发回执。回执不按
Job 复制；可重新处理的跳过或失败回执会把 `sync_job_id` 更新为最近处理尝试。终态 payload
幂等仍由回执唯一约束和快照 payload 哈希共同保证。

## 前端提示与轮询

Garmin 页面把自动快照作为同步任务的次级状态展示：

- PROCESSING：训练数据已同步，正在更新训练状态；
- CREATED：训练状态历史已更新，并可前往 `/runner-state`；
- DUPLICATE_PAYLOAD：当前状态未变化，无需新增历史；
- SKIPPED_NO_MATERIAL_CHANGE：本次同步没有影响状态的新数据；
- SKIPPED_NOT_COMMITTED：本次同步未提交训练数据；
- FAILED_NON_BLOCKING：训练数据已同步，状态历史暂未更新。

Job 终态而回执仍为 PROCESSING 时，页面最多额外轮询 8 次，每次沿用 2.5 秒间隔；终态回执或
达到上限后停止，不进行无限轮询。FAILED_NON_BLOCKING 使用次要警告样式，不把同步主状态显示
为失败。Today 页面仍只提示“已创建同步任务”，不提前宣称快照成功。

## 无回执与历史页面兼容

`runner_state_snapshot=null` 是正常兼容状态，不显示失败或“未处理”。GARMIN_SYNC 创建的快照
沿用既有历史列表、Timeline 和详情接口；详情读取保存内容，不重新计算。回执本身不进入快照
列表。手动快照继续显示“手动保存”。

## 当前限制

- 不自动重试 FAILED_NON_BLOCKING；
- 不支持其他 Provider 自动快照；
- 不为 reconcile、resolve、restore 或 reprocess 创建快照；
- 不在 Job 表重复持久化快照状态；
- 不提供公共回执管理 API；
- 不使用大语言模型生成同步或状态摘要。

