# Runner State Garmin Pipeline 接入学习说明

## 为什么只能在 Pipeline 接入

Garmin API 的 BackgroundTask 和独立 Worker 都通过 `ActivitySyncPipeline` 执行同一任务。若在
路由或 Worker 分别调用快照，会造成入口行为不一致，并可能让同一 Job 生成两次触发。Pipeline
是“任务已领取、同步事务已结束、即将把结果交还调用方”的共同边界，因此是唯一安全接入点。

## 为什么使用独立 Session

Garmin 同步的 Session A 决定训练数据与 Job 终态。自动快照属于可失败的后置能力，使用
Session B 可以保证：

- 快照计算能看到 Session A 已提交的新日志；
- 快照失败不能回滚训练数据；
- 回执事务可以独立 rollback；
- BackgroundTask 和 Worker 得到相同的失败隔离行为。

排查时先确认 Session B 只在 `sync_outcome.claimed` 为真后创建，并在 `finally` 中关闭。

## Outcome 如何进入自动快照

`garmin_sync_service._outcome_from_job` 从服务端 Job 构建内部 Outcome，其中包含可信 `user_id`、
Provider、稳定 `sync_run_id`、`committed` 和 Runner State material change 数量。Pipeline 不修改
这些值，而是逐项传给 `RunnerStateAutoSnapshotService.process_garmin_sync_outcome`。

自动服务负责判断创建、payload 重复、没有有效变化、未提交和非阻塞失败。Pipeline 不重复一套
状态规则。

## 为什么不在 Job 表重复保存结果

回执表已经承担触发幂等、处理租约、最终状态和快照引用。若把 snapshot status、snapshot id 或
error 再存入 Job 表，会出现两份事实和更新顺序竞争。Job API 通过只读查询服务在响应时装配回执
摘要，既保持单一事实来源，又不改变 Job 表结构。

## 回执如何批量查询

详情使用 `get_for_sync_run`。列表使用 `get_for_sync_runs`：

1. 过滤当前页 Garmin Job；
2. 对 sync_run_id 去重；
3. 构造 trigger reference；
4. 执行一次 `IN (...)` 查询，并限定当前 user_id 和 GARMIN_SYNC；
5. 建立 sync_run_id 到公开摘要的映射；
6. 线性装配所有 Job。

不要在循环中调用单条查询，也不要加载 snapshot 关系或 payload。

## Retry 为什么共享结果

retry Job 是同一次逻辑同步的另一次执行尝试，继承原 `sync_run_id`。触发回执唯一键以当前用户、
GARMIN_SYNC 和 trigger reference 为准，所以初始 Job 与 retry Job 自然看到同一结果。不要复制
回执，也不要改成按 Job ID 查询。

## FAILED_NON_BLOCKING 如何展示

它表示训练同步主流程可能已经成功，但状态历史后置处理没有完成。前端应保持 Job 的真实主状态，
在次级区域显示“训练数据已同步，状态历史暂未更新”，使用轻量警告而不是红色同步失败提示。
错误码可供排查，但不得把内部异常消息呈现给用户。

## 如何排查回执为 null

依次检查：

1. Job 是否为 Garmin；
2. Job 是否仍为 queued，或是否从未被成功领取；
3. 是否为上线前旧 Job；
4. Pipeline 是否在自动快照阶段前终止；
5. sync_run_id 是否为服务端生成的规范 UUID；
6. 查询是否带正确 current user；
7. API 列表是否经过批量装配服务。

null 是兼容状态，不能直接判定为系统错误。

## 如何排查 PROCESSING 长时间不结束

检查 receipt 的 locked_at、处理租约、Worker 日志中的安全错误码和 Session B 数据库连通性。
前端只做有上限的短轮询，不负责重领租约。当前版本不自动重试 FAILED_NON_BLOCKING，人工重试
同步时由既有回执状态机判断是否可重新处理。

## 如何扩展新 Provider

先为新 Provider 建立稳定的逻辑运行 ID、可信 user_id、commit 结果和 Runner State material
change 契约；再为其定义独立触发类型和回执查询映射。只有在所有入口都经过同一 Pipeline 时，
才能复用此后置模式。不要直接把 Garmin trigger reference 前缀用于其他 Provider。

## 如何测试失败隔离

至少注入以下故障：Session B 创建失败、自动服务构造失败、状态计算失败、序列化失败、快照写入
失败和回执完成失败。每项都应验证：

- Provider 只执行一次；
- sync_outcome 对象和值不变；
- Job 终态不变；
- Session B rollback/close；
- 返回 FAILED_NON_BLOCKING 或持久化的等价状态；
- 日志不包含 Token、payload、Evidence 或数据库凭据。

## 项目负责人验收清单

- [ ] 自动快照只在 `ActivitySyncPipeline.run_job` 调用；
- [ ] claimed=false 不创建 Session B；
- [ ] user_id 来自服务端 Job/Outcome；
- [ ] BackgroundTask 和 Worker 不二次调用自动服务；
- [ ] Session A 提交后才创建 Session B；
- [ ] 意外异常不改变同步 Job；
- [ ] 列表回执查询为一次批量查询；
- [ ] API 嵌套字段只有 status、snapshot_id、error_code；
- [ ] retry Job 共享 sync_run_id 结果；
- [ ] 前端 PROCESSING 轮询有明确上限；
- [ ] FAILED_NON_BLOCKING 不显示为 Garmin 同步失败；
- [ ] Today 不提前宣称快照成功；
- [ ] GARMIN_SYNC 快照自然进入既有历史 Timeline；
- [ ] 未新增 Job 字段或数据库迁移；
- [ ] 未修改 Runner State 规则、canonical JSON 和 payload 哈希。

