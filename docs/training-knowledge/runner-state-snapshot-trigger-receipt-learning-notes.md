# Runner State 自动快照回执学习说明

## 1. 为什么需要独立回执表

快照是状态档案，回执是事件处理档案。两个 `sync_run_id` 可能得到同一 payload：数据库只需一张状态快照，但每次同步都要留下处理结论。若只给快照表增加 trigger 唯一约束，就无法同时表达事件幂等和内容幂等，还可能迫使系统修改旧快照。

## 2. sync_run_id、Job ID 与 receipt ID

- `sync_run_id`：一次逻辑同步的服务器 UUID，跨重试不变，用于 trigger reference；
- Job ID：某次具体尝试，重试会变化，回执只保存最近一次；
- receipt ID：自动快照处理记录，同一逻辑同步始终只有一个。

trigger reference 固定为 `garmin-sync:<sync_run_id>`。时间戳每次重试都会不同，Job ID 会把一次逻辑同步拆成多次事件，都不能作为此处的幂等身份。

## 3. 首次领取、租约与 token

领取不是先 SELECT 再 INSERT。调用者直接插入同一唯一键，数据库只允许一个成功；失败者只把指定唯一约束识别为已有回执，其他完整性错误不会冒充重复。

成功插入会提交事务 A，让其他 Worker 看到 `PROCESSING`。Worker 崩溃时，15 分钟后恢复者用 `id + PROCESSING + 旧 locked_at + 已过期` 条件 UPDATE 竞争，只有 `rowcount == 1` 获得新 token。

完成时必须同时匹配 token。假设 A 超时、B 恢复并成功，迟到的 A 仍持旧 token，无法覆盖 B。仅按 receipt ID 更新会破坏这项保证。

## 4. 为什么跳过状态可以重新打开

`SKIPPED_NOT_COMMITTED`、`SKIPPED_NO_MATERIAL_CHANGE` 和 `FAILED_NON_BLOCKING` 不是永久完成状态。同一 sync run 的第一次 Job 可能失败或没有变化，第二次重试可能提交新事实。重新领取更新原回执、增加 `attempt_count`，不创建第二条。

`CREATED` 与 `DUPLICATE_PAYLOAD` 才是终态；再次调用直接返回 `ALREADY_PROCESSED_TRIGGER`。

## 5. 快照与回执如何原子提交

事务 B 数据流：

```text
验证 receipt token
  -> RunnerStateService.get_current
  -> 既有 serializer / canonical JSON / SHA-256
  -> create_or_get_snapshot_in_transaction（只 flush）
  -> 条件完成 receipt
  -> 同一个 commit
```

新快照与 `CREATED` 一起提交。payload 已存在时不修改旧快照，回执以 `DUPLICATE_PAYLOAD` 指向它。完成回执失败会 rollback 新快照，避免“快照已保存、回执仍 PROCESSING”。

## 6. 失败如何隔离

阶段 B 异常先 rollback，再用干净事务按当前 token 写 `FAILED_NON_BLOCKING`。固定错误码区分计算、序列化、快照持久化、回执完成和事务失败；异常原文不会直接写入回执或结果。

回执失败本身若无法保存，服务仍返回非阻塞失败并写安全日志，但不伪装成 CREATED。整个过程不更新 `ExternalSyncJob`，未来接入后不会把成功的 Garmin 同步改成失败。

## 7. payload 重复如何映射

同步运行 B 可能与运行 A 或手动保存得到同一 payload。此时沿用 `(user_id, data_cutoff_date, payload_hash)` 的快照去重，B 的回执为 `DUPLICATE_PAYLOAD` 并指向旧 snapshot ID。旧快照的 trigger type/reference 保持不变。

## 8. 如何扩展 DAILY 或 PLAN_ADJUSTMENT

新触发源应定义服务器生成的稳定 reference、可信输入和调用边界，再复用领取与快照事务。不得把 trigger type/reference 或 user_id 暴露给公共手动 API。

扩展时需新增 reference、重放、并发、租约、跳过/失败重试及 commit 后接入测试，并明确何种变化属于 material change。

## 9. 如何测试 MySQL 并发

使用隔离 MySQL 数据库和独立 Session：第一个 Worker 领取后暂停，第二个处理同一 trigger，验证只有一个回执；再构造过期租约，验证 attempt 只增加一次；最后用旧 token 完成，验证 rowcount 为 0。测试结束删除临时数据库。

SQLite 可做纯逻辑测试，但不能替代 MySQL 的唯一冲突、外键、条件更新和 DDL 升降级验收。

## 10. 项目负责人验收清单

- [ ] 快照 payload 唯一约束与哈希语义未改变；
- [ ] 回执只有一个 trigger 唯一约束和四个指定普通索引；
- [ ] 同一 trigger 并发只有一个处理者；
- [ ] 未提交与无变化不调用 Runner State；
- [ ] 跳过和失败可重试；
- [ ] 过期租约可恢复，旧 token 不能完成；
- [ ] payload 重复指向旧快照且不修改其 trigger；
- [ ] 新快照和回执终态同事务提交；
- [ ] 自动失败不修改同步 Job；
- [ ] 手动 POST 固定 MANUAL，current GET 只读；
- [ ] MySQL 5.7 与 8 完成升降级、再升级及并发验证；
- [ ] Pipeline、Worker、路由和前端仍未接入；
- [ ] 数据全部虚构，日志与仓库无敏感信息。
