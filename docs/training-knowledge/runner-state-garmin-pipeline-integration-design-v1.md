Garmin 同步后 Runner State 自动快照接入设计 v1

对应版本：GaitLogic v0.10.3-C2.3-C
文档状态：设计确认稿
前置阶段：

C2.3-A Garmin 同步事务与 Material Change
C2.3-B 自动快照服务与触发回执
1. 设计目标

C2.3-C 将 RunnerStateAutoSnapshotService 接入 Garmin 同步统一执行链路。

完成后：

Garmin 同步
→ 训练数据提交
→ 生成 GarminSyncRunOutcome
→ 自动处理 Runner State 快照
→ 保存触发回执
→ 同步任务查询返回快照结果
→ 前端展示非阻塞提示

本阶段实现：

Pipeline 自动快照编排；
独立 Session 与失败隔离；
BackgroundTask 和轮询 Worker 一致行为；
同步任务响应返回自动快照摘要；
Garmin 页面展示处理结果；
Today 页面保持兼容；
历史页面自然展示 Garmin 快照；
后端、前端、MySQL 5.7/8 完整回归。

本阶段不实现：

自动修改训练计划；
Agent；
每日定时快照；
reconcile、resolve、restore 自动快照；
自动重试失败回执；
新的 Runner State 页面；
大语言模型总结。
2. 核心原则
2.1 Pipeline 是唯一接入点

唯一允许调用自动快照服务的位置：

server/integrations/activity_sync/pipeline.py
ActivitySyncPipeline.run_job

禁止分别在以下位置调用：

Garmin API 路由；
BackgroundTask；
轮询 Worker；
单活动处理循环；
run_sync_job() 主事务内部；
前端轮询逻辑。

统一链路：

BackgroundTask ─┐
                ├→ ActivitySyncPipeline.run_job
轮询 Worker ────┘
                       ↓
             Garmin 同步事务完成
                       ↓
             GarminSyncRunOutcome
                       ↓
             自动快照后置处理

这样两套执行入口不会一个保存快照、另一个装作没看见。

3. 调用前提

只有满足：

outcome.claimed = true

才处理自动快照。

未领取任务：

claimed = false

必须直接返回，不创建回执，不计算状态。

对于已经领取的任务，无论最终状态为：

succeeded
partially_succeeded
failed

都将真实的：

committed
runner_state_affecting_change_count

交给自动快照服务。

由自动服务决定：

创建快照；
复用快照；
无变化跳过；
未提交跳过；
非阻塞失败。

Pipeline 不复制判断规则。

4. 事务与 Session 边界
Session A：Garmin 同步

负责：

任务领取；
Garmin 数据拉取；
ExternalActivity；
WorkoutLog；
关联和复合汇总；
Material Change；
同步任务终态；
主事务 commit 或 rollback。

完成后返回：

GarminSyncRunOutcome
Session B：Runner State 自动快照

负责：

领取触发回执；
计算当前 Runner State；
创建或复用快照；
完成回执；
失败记录。

要求：

Session B 必须独立于 Session A；
Session A 结束后才能创建 Session B；
自动快照异常不得 rollback Session A；
自动快照不得改变 ExternalSyncJob 状态；
Session B 使用 SessionLocal 或项目统一 Session 工厂；
Session B 完成后必须关闭；
异常时必须 rollback。

推荐流程：

Session A
→ run_sync_job
→ commit/rollback
→ 返回 outcome
→ 结束同步 Session 工作

Session B
→ process_garmin_sync_outcome
→ commit/rollback
→ 关闭
5. Pipeline 编排结果

建议 Pipeline 返回新的组合结果：

ActivitySyncPipelineResult

结构：

sync_outcome: GarminSyncRunOutcome
runner_state_snapshot: RunnerStateAutoSnapshotResult | null

语义：

情况	runner_state_snapshot
未领取任务	null
已领取且自动处理完成	对应结果
自动服务意外失败	FAILED_NON_BLOCKING
本阶段未启用的 Provider	null

本阶段仅 Garmin Provider 启用 Runner State 自动快照。

其他 Provider 不得因为共用 Pipeline 被意外接入。

6. 自动快照调用参数

Pipeline 从 GarminSyncRunOutcome 读取：

user_id
job_id
sync_run_id
committed
runner_state_affecting_change_count

调用：

process_garmin_sync_outcome(
    user_id=user_id,
    sync_job_id=outcome.job_id,
    sync_run_id=outcome.sync_run_id,
    committed=outcome.committed,
    material_change_count=outcome.runner_state_affecting_change_count,
)

不得从客户端请求读取：

user_id；
sync_run_id；
trigger type；
trigger reference；
material change count。

这些字段只能来自服务端同步结果。

7. Pipeline 失败隔离

自动快照服务本身已经返回：

FAILED_NON_BLOCKING

Pipeline 仍应提供最后一道隔离。

若自动服务在调用边界外抛出非预期异常：

catch
→ rollback Session B
→ 安全日志
→ 构造 FAILED_NON_BLOCKING 结果
→ 保留 sync_outcome

不得：

将同步任务从 succeeded 改成 failed；
覆盖 safe_error_message；
把异常重新抛给 BackgroundTask 导致任务被视为失败；
重跑 Garmin 同步；
返回完整异常信息给前端。

日志允许包含：

job_id
sync_run_id
user_id
安全 error_code

禁止包含：

Token；
原始 Garmin payload；
Runner State payload；
Evidence；
数据库密码。
8. 回执作为自动快照结果来源

不在 ExternalSyncJob 重复存储：

snapshot_status
snapshot_id
snapshot_error_code

自动快照结果只保存在：

runner_state_snapshot_trigger_receipt

同步任务通过：

ExternalSyncJob.sync_run_id
→ garmin-sync:<sync_run_id>
→ receipt

查询。

原因：

回执已经是自动快照处理的权威记录；
避免 Job 与回执结果不一致；
retry Job 共享同一 sync_run_id；
不同 Job 尝试最终映射到同一回执。
9. 同步任务响应扩展

现有：

ExternalSyncJobRead

新增可选嵌套字段：

{
  "runner_state_snapshot": {
    "status": "CREATED",
    "snapshot_id": 123,
    "error_code": null
  }
}

建议 Schema：

RunnerStateSnapshotSyncResultRead

字段：

status
snapshot_id
error_code

不返回：

receipt_id；
user_id；
trigger_reference；
processing_token；
locked_at；
attempt_count；
safe_error_message 内部细节；
完整快照 payload。
10. 同步结果状态映射

数据库回执到 API：

回执状态	API 状态
PROCESSING	PROCESSING
CREATED	CREATED
DUPLICATE_PAYLOAD	DUPLICATE_PAYLOAD
SKIPPED_NO_MATERIAL_CHANGE	SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_NOT_COMMITTED	SKIPPED_NOT_COMMITTED
FAILED_NON_BLOCKING	FAILED_NON_BLOCKING
无回执	null

以下内部状态不落数据库，因此不直接由任务查询返回：

ALREADY_PROCESSED_TRIGGER
PROCESSING_BY_ANOTHER_WORKER

查询时直接返回已有回执的真实数据库状态。

11. API 查询装配

以下接口返回 ExternalSyncJobRead 时，均应装配自动快照摘要：

Garmin 同步任务详情；
通用同步任务详情；
Garmin 同步任务列表；
通用同步任务列表；
retry 返回的新 Job；
页面轮询使用的任务查询。

要求：

同一套 Schema；
同一套装配服务；
不在每个路由重复查询；
列表查询避免 N+1；
通过批量 sync_run_id 查询回执；
无回执时返回 null；
不重新计算 Runner State；
不创建回执；
GET 保持只读。

建议增加：

RunnerStateReceiptQueryService

或在现有 Facade 中提供批量装配能力。

12. Retry 语义

同一逻辑同步：

Job 101 failed
Job 105 retry succeeded

两者共享：

sync_run_id

因此查询 Job 101 和 Job 105 时，可能都返回同一个最终回执结果。

这是正确语义：

自动快照结果属于逻辑同步运行，不属于某一次 Job 尝试。

前端可在具体 Job 上展示该运行的最终 Runner State 处理结果。

不得为每个 retry Job 创建第二条回执。

13. BackgroundTask 与 Worker

两者必须继续只调用：

ActivitySyncPipeline.run_job

不得在调用方追加：

run_job(...)
process_auto_snapshot(...)

否则调用方又开始分叉，工程师过几个月便会发现某条路径少了一行，然后举行深夜调试仪式。

验证：

BackgroundTask 触发自动快照；
Worker 触发自动快照；
同一 Job 并发执行时只有领取者触发；
未领取者不创建 Session B；
两个入口返回或记录一致结果。
14. Frontend 类型

扩展：

ExternalSyncJobRead

新增可选字段：

runner_state_snapshot?: {
  status:
    | 'PROCESSING'
    | 'CREATED'
    | 'DUPLICATE_PAYLOAD'
    | 'SKIPPED_NO_MATERIAL_CHANGE'
    | 'SKIPPED_NOT_COMMITTED'
    | 'FAILED_NON_BLOCKING'
  snapshot_id: number | null
  error_code: string | null
} | null

不得使用 string 代替明确联合类型。

15. Garmin 页面提示

Garmin 同步页面在任务进入终态后显示自动快照结果。

CREATED
训练状态历史已更新

样式：

成功或中性成功；
可提供“查看训练状态”入口；
跳转 /runner-state，默认行为遵循现有页面。
DUPLICATE_PAYLOAD
当前训练状态未发生变化，无需新增历史记录

使用中性提示。

SKIPPED_NO_MATERIAL_CHANGE
本次同步未产生影响训练状态的新数据

使用中性提示。

SKIPPED_NOT_COMMITTED
本次同步未提交训练数据，因此未更新训练状态

同步任务本身若失败，主错误仍按现有逻辑显示。

PROCESSING
训练数据已同步，正在更新训练状态

保持轮询。

FAILED_NON_BLOCKING
训练数据已同步，状态历史暂未更新

必须使用次要警告。

禁止显示：

Garmin 同步失败

除非同步 Job 自身确实失败。

16. Today 页面

Today 页面当前只提示：

已创建同步任务

本阶段不强制为 Today 页面增加完整轮询。

要求：

类型兼容新增字段；
不在任务刚排队时声称状态历史已经更新；
不显示错误快照结果；
可保留当前提示；
后续进入 Garmin 页面查看详细结果。
17. 历史页面

现有 Runner State 历史页已经支持：

GARMIN_SYNC → Garmin同步

C2.3-C 不修改历史页面主要结构。

只需验证：

新快照出现在 Timeline；
原始列表触发方式显示“Garmin同步”；
详情显示当时保存的数据；
DUPLICATE_PAYLOAD 不产生第二条快照；
回执不直接出现在历史快照列表中。
18. PROCESSING 查询语义

Pipeline 在事务 A 创建回执并提交后，事务 B 可能仍在处理。

API 查询可能暂时看到：

PROCESSING

这是正常状态。

前端轮询停止条件：

CREATED
DUPLICATE_PAYLOAD
SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_NOT_COMMITTED
FAILED_NON_BLOCKING

PROCESSING 继续轮询，但必须有现有任务轮询的超时或停止机制，不能无限请求到宇宙热寂。

19. 无回执情况

可能出现：

旧同步 Job 在 C2.3-C 上线前完成；
Job 未被领取；
非 Garmin Provider；
Pipeline 在回执阶段前意外终止；
数据迁移前的历史任务。

返回：

runner_state_snapshot = null

前端不得将 null 显示为失败。

20. 前端组件建议

根据现有 Garmin 页面结构增加等价组件：

RunnerStateSnapshotSyncStatus

职责：

接收同步任务的嵌套结果；
映射中文文案；
映射轻量状态样式；
提供可选跳转；
不调用 API；
不计算业务状态。

状态映射集中管理，不能散落在页面模板中。

21. API 性能

列表接口批量查询回执：

WHERE user_id = :current_user
AND trigger_type = 'GARMIN_SYNC'
AND trigger_reference IN (...)

要求：

使用回执唯一索引；
不加载快照 payload；
只读取状态、snapshot_id、error_code 和 trigger_reference；
不发生 N+1；
不为 null sync_run_id 拼接引用；
结果映射复杂度保持线性。
22. 安全与权限
只能查询当前用户同步任务对应的回执；
不能通过其他用户的 sync_run_id 查询；
API 不增加独立 receipt ID 查询；
不暴露 trigger reference；
不暴露 processing token；
不暴露锁时间；
不暴露数据库错误；
不允许客户端创建或修改回执；
不允许客户端伪造自动快照结果；
不记录完整 payload。
23. 后端测试
Pipeline 接入
claimed=false 不调用自动快照；
claimed=true 调用一次；
succeeded 有变化创建快照；
succeeded 无变化跳过；
partially_succeeded 有变化创建；
failed 且未提交跳过；
自动服务失败不改变 sync outcome；
一次 Pipeline 运行最多处理一次回执；
多活动仍只生成一张快照；
BackgroundTask 和 Worker 行为一致。
Session 与失败隔离
自动快照使用独立 Session；
Session B 失败不影响 Session A；
Session B 正确关闭；
Session B 异常 rollback；
自动快照异常不改变 Job 状态；
自动快照异常不重新执行 Garmin Provider。
API
任务详情返回嵌套结果；
任务列表批量返回结果；
无回执返回 null；
PROCESSING 返回正确；
CREATED 返回 snapshot_id；
FAILED 返回安全 error_code；
不返回 trigger reference；
不返回 processing token；
只查询当前用户；
retry Job 返回同一逻辑运行的结果；
列表无 N+1。
回归
手动快照仍正常；
Timeline 正常显示 Garmin 快照；
payload 重复不新增快照；
current GET 只读；
C2.3-A 测试通过；
C2.3-B 测试通过；
完整 pytest 通过。
24. 前端测试
ExternalSyncJob 类型支持嵌套字段；
CREATED 文案；
DUPLICATE 文案；
NO MATERIAL CHANGE 文案；
NOT COMMITTED 文案；
PROCESSING 文案；
FAILED_NON_BLOCKING 文案；
FAILED_NON_BLOCKING 不显示同步失败；
null 不显示错误；
CREATED 可跳转训练状态页；
页面轮询后更新结果；
旧任务无字段时兼容；
Today 页面不提前宣称快照成功；
移动端布局；
TypeScript 通过；
生产构建通过。

所有测试使用虚构数据。

25. MySQL 验证

在 MySQL 5.7 和 MySQL 8 验证：

同步任务提交；
回执创建；
快照创建；
payload 重复；
retry 共享回执；
并发领取；
Pipeline 后置事务；
回执批量查询；
外键；
完整迁移链；
downgrade；
再次 upgrade。

不得触发真实 Garmin API。

26. 文档

新增：

docs/training-knowledge/runner-state-garmin-pipeline-integration-v1.md

包含：

Pipeline 接入点；
两个 Session；
Pipeline 组合结果；
回执查询；
API 嵌套结果；
前端提示；
retry 语义；
失败隔离；
当前限制。

新增：

docs/training-knowledge/runner-state-garmin-pipeline-integration-learning-notes.md

说明：

为什么只能在 Pipeline 接入；
为什么必须独立 Session；
如何从 outcome 调用自动快照；
为什么不把结果重复存到 Job；
API 如何批量装配；
retry 为什么共享回执；
FAILED_NON_BLOCKING 如何展示；
如何调试回执缺失；
如何扩展其他 Provider；
项目负责人验收清单。

更新公开竞赛架构文档，只描述公开工程架构。

27. 开源边界

允许公开：

Pipeline 编排；
回执查询；
API Schema；
前端状态组件；
虚构测试；
技术文档。

保持私有：

真实回执；
真实同步任务；
用户状态历史；
自动快照成功率；
用户训练变化统计；
竞赛实验数据。

两个仓库均禁止：

Garmin Token；
API Key；
数据库密码；
原始活动数据；
邮箱；
手机号；
用户身份映射。
28. 验收标准

C2.3-C 完成后必须满足：

Pipeline 是唯一接入点；
BackgroundTask 和 Worker 行为一致；
未领取任务不处理快照；
同步提交后才处理快照；
自动快照使用独立 Session；
自动快照失败不影响同步结果；
一次同步最多创建一条回执和一条状态结果；
同步结果通过回执表查询；
Job 表不重复存快照结果；
任务 API 返回可选嵌套结果；
列表查询无 N+1；
前端正确展示所有状态；
FAILED_NON_BLOCKING 不显示为同步失败；
历史页面自动显示 Garmin 快照；
公共手动保存不退化；
不新增客户端写回执接口；
不修改快照哈希；
不修改 Runner State 规则；
MySQL 5.7/8 通过；
完整测试通过。
29. 实施顺序
1. Pipeline 组合结果
2. 独立 Session 自动快照编排
3. BackgroundTask 与 Worker 回归
4. 回执只读查询服务
5. 同步任务 Schema 扩展
6. 单任务查询装配
7. 列表批量装配
8. 前端类型
9. Garmin 状态提示组件
10. Garmin 页面接入
11. Today 页面兼容
12. 后端测试
13. 前端测试
14. MySQL 5.7/8 验证
15. 完整回归
16. 文档
30. 设计结论

C2.3-C 完成后，Garmin 同步与 Runner State 历史正式形成自动闭环：

同步训练事实
→ 判断是否真正影响跑者状态
→ 自动保存或复用状态快照
→ 记录事件处理回执
→ 用户在同步页看到结果
→ 用户在历史页查看变化