# Garmin 同步事务与 Material Change 学习说明

## 1. 两类执行入口如何统一

API 创建任务后，BackgroundTask 调用 `server/integrations/activity_sync/workers/sync_worker.py`。常驻轮询进程位于 `server/workers/external_sync_worker.py`。它们都进入 `ActivitySyncPipeline`，再调用同一个 `garmin_sync_service.run_sync_job()`。以后修同步业务时，不应在 Worker 或路由里复制处理逻辑。

retry 路由当前只入队。这是两套 API 的统一产品约定；轮询 Worker 负责后续执行。

## 2. Job 如何原子领取

`claim_sync_job()` 不使用“先 SELECT、再判断、再 UPDATE”的应用层竞争方案。它直接执行 `status='queued'` 条件更新，并检查受影响行数。两个线程同时领取时，第一个把状态改成 running，第二个条件不再成立。

领取事务提交后调用 `expire_all()`，避免 `expire_on_commit=False` 的 Session 继续持有旧 queued 状态。

## 3. 为什么 running Job 不能再次执行

running 表示已有执行者持有执行权。若第二个执行者也接受 running，会重复拉取、重复刷新 Token，并可能并发写同一活动。现在第二个执行者返回 `JOB_NOT_CLAIMED`，在 Provider 创建之前结束。

## 4. fatal rollback 如何工作

活动处理使用保存点只是为了允许“单条失败、其他成功”。保存点不等于主事务已经提交。当 Provider 刷新、外层数据库操作或其他致命步骤失败时：

1. `rollback()` 撤销全部尚未提交的训练事实；
2. 重新查询 Job，开始干净事务；
3. 只写入失败状态和安全错误信息；
4. 提交失败标记。

旧实现直接在 `_fail_job()` 中 commit，可能把同一 Session 中尚未提交的训练数据一起提交；新主链路不再使用这种方式。

## 5. commit 失败如何恢复

最终 commit 可能因连接或数据库错误失败。此时 Session 必须先 rollback 才能恢复。随后 `_mark_job_failed()` 在干净事务中写入 `failed`、`is_committed=false` 和 `SYNC_COMMIT_FAILED`。若失败标记本身也无法提交，异常继续向上抛出，不能伪装成功。

## 6. sync_run_id 与 Job ID

- Job ID：一次尝试的数据库主键；
- `sync_run_id`：同一次逻辑同步跨多次重试的 UUID；
- Idempotency-Key：客户端避免重复入队的现有契约。

三者不能互相替代。首次 Job 由服务端生成 UUID，retry 创建新 Job 并继承 UUID。历史数据升级也逐行生成 UUID，不使用时间戳、Job ID 或客户端键。

## 7. before/after 投影比较

Tracker 第一次遇到既有 WorkoutLog 时保存 before。所有活动、关联和复合汇总结束后，统一从 ORM 对象读取 final after。只有 Runner State 依赖字段进入投影。

举例：Garmin payload 新增步频会更新 ExternalActivity，但若 WorkoutLog 的状态、日期、类型、距离、时长、RPE 和心率都未变化，material change 为 0。

## 8. 复合日志如何避免重复计数

每条活动先使用局部 Tracker。保存点成功后才合并到全局 Tracker。全局 Tracker 以 WorkoutLog ID 为键，保留最早 before 和最终对象，因此同一日志由热身、主训练、放松三段依次更新时仍只产生一个 created 或 updated 计数。

若一条活动保存点回滚，它的局部 Tracker 不会合并。若主事务回滚，结果字段也不会提交，失败标记会把 material 计数重置为 0。

## 9. 如何增加新的 Runner State 相关字段

1. 先确认 Runner State 查询与聚合确实读取该字段；
2. 把字段加入 `RunnerStateRelevantWorkoutLogProjection`；
3. 在 `from_workout_log()` 中定义稳定规范化；
4. 增加“字段变化会计数”的参数化测试；
5. 增加等价类型值、null 与 0 的测试；
6. 检查复合日志仍只计一次；
7. 更新技术文档字段表。

不要用 ORM dirty、`updated_at` 或原始 payload hash 替代业务投影。

## 10. 如何测试事务与并发

事务、并发和升级测试必须使用随机命名的隔离 MySQL 数据库，并 Mock Garmin Provider。重点断言数据库最终状态，而不是只断言函数返回：

- 双线程领取只有一个成功，attempt_count 为 1；
- 单活动失败、其他成功时只提交成功数据；
- 全部失败、fatal 和 commit 失败时不存在 WorkoutLog 半记录；
- 无活动时 committed 为 true、material 为 0；
- upgrade、downgrade、再 upgrade 均成功；
- 历史 Job UUID 非空、合法且逐行独立。

测试结束必须删除临时库，禁止连接真实 Garmin 或使用真实用户数据。

## 11. 项目负责人验收清单

- [ ] 两个 API 创建任务后行为一致；
- [ ] BackgroundTask 与轮询 Worker 都经过 Pipeline；
- [ ] running Job 不会再次调用 Provider；
- [ ] retry 新 Job 继承 `sync_run_id`；
- [ ] 客户端不能提交 `sync_run_id`；
- [ ] 致命异常和 commit 失败没有训练半记录；
- [ ] 部分成功语义与持久化状态一致；
- [ ] material 投影只含 Runner State 依赖字段；
- [ ] 复合日志只计一次；
- [ ] API 未暴露 Token、payload 或内部异常；
- [ ] 本阶段没有调用快照服务或创建自动快照；
- [ ] MySQL 升降级只在隔离库验证；
- [ ] 完整后端、前端与安全检查通过。

