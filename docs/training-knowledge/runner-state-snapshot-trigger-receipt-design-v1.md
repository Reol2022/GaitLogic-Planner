Runner State 自动快照触发回执设计 v1

对应版本：GaitLogic v0.10.3-C2.3-B
文档状态：设计确认稿
前置阶段：

C2.1 历史快照
C2.2 历史趋势展示
C2.3-A Garmin 同步事务与 Material Change 契约
1. 设计目标

C2.3-B 建立一套内部能力，使系统能够根据一次 Garmin 逻辑同步运行，幂等地处理 Runner State 快照。

本阶段实现：

触发回执表；
内部自动快照服务；
GARMIN_SYNC 触发语义；
同步运行级幂等；
快照内容级幂等；
并发领取；
失败回执；
可恢复状态；
MySQL 5.7/8 升降级；
单元测试和事务测试。

本阶段不实现：

Garmin Pipeline 正式调用；
BackgroundTask 或 Worker 自动触发；
前端同步提示；
API 返回快照结果；
自动调整训练计划；
大语言模型训练分析；
新的历史页面。
2. 为什么需要独立回执表

快照记录：

某一时刻，跑者的状态是什么。

回执记录：

某一次外部事件，是否已经处理过，以及处理结果是什么。

两者不是同一种事实。

例如：

同步运行 A
→ 计算状态 X
→ 创建快照 100

同步运行 B
→ 训练事实发生变化
→ 计算结果仍然是状态 X
→ payload hash 命中快照 100

同步运行 B 不能创建重复快照，但必须留下处理结果：

DUPLICATE_PAYLOAD
snapshot_id = 100

因此不能只依赖快照表：

UNIQUE(user_id, data_cutoff_date, payload_hash)

也不应修改旧快照的 trigger_reference，因为历史快照必须保持不可变。

3. 数据模型

新增表：

runner_state_snapshot_trigger_receipt

建议 ORM 名称：

RunnerStateSnapshotTriggerReceipt
3.1 字段
字段	类型	说明
id	BIGINT	主键
user_id	BIGINT	当前用户
trigger_type	VARCHAR(32)	当前仅使用 GARMIN_SYNC
trigger_reference	VARCHAR(128)	garmin-sync:<sync_run_id>
status	VARCHAR(40)	当前处理状态
snapshot_id	BIGINT NULL	创建或复用的快照
sync_job_id	BIGINT NULL	最近一次处理该运行的 Job
material_change_count	INT	当前观察到的有效变化数
is_committed	BOOLEAN	同步主事务是否成功提交
attempt_count	INT	回执处理尝试次数
processing_token	VARCHAR(36) NULL	当前处理者令牌
locked_at	DATETIME NULL	处理租约开始时间
completed_at	DATETIME NULL	当前结果完成时间
error_code	VARCHAR(64) NULL	安全错误码
safe_error_message	VARCHAR(255) NULL	脱敏错误说明
created_at	DATETIME	创建时间
updated_at	DATETIME	更新时间
3.2 约束

唯一约束：

UNIQUE(user_id, trigger_type, trigger_reference)

索引：

INDEX(user_id, created_at)
INDEX(sync_job_id)
INDEX(status, locked_at)
INDEX(snapshot_id)

检查约束或应用层校验：

material_change_count >= 0
attempt_count >= 0
4. 外键语义
user_id
FOREIGN KEY → user_account.id
ON DELETE CASCADE

用户删除后，其快照与触发回执一并删除。

snapshot_id
FOREIGN KEY → runner_state_snapshot.id
ON DELETE SET NULL

快照当前没有删除接口，但保留 SET NULL 可避免未来维护行为破坏回执记录。

sync_job_id
FOREIGN KEY → external_sync_job.id
ON DELETE SET NULL

回执的核心身份是 sync_run_id 对应的 trigger_reference，不是某一次具体 Job。

5. 触发引用

Garmin 自动快照固定使用：

trigger_type = GARMIN_SYNC
trigger_reference = garmin-sync:<sync_run_id>

示例：

garmin-sync:cb64dbbf-6a2d-41b8-b697-3d9268b85f48

要求：

sync_run_id 来自 C2.3-A；
由服务器生成；
跨重试保持一致；
不使用 Job ID；
不使用客户端 Idempotency-Key；
不使用时间戳；
不包含 Token、邮箱、手机号或 Garmin 外部活动 ID。
6. 回执状态

数据库状态定义：

PROCESSING
CREATED
DUPLICATE_PAYLOAD
SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_NOT_COMMITTED
FAILED_NON_BLOCKING
状态语义
状态	含义	是否终态
PROCESSING	某个处理者正在执行	否
CREATED	创建了新快照	是
DUPLICATE_PAYLOAD	状态内容已存在，复用旧快照	是
SKIPPED_NO_MATERIAL_CHANGE	当前 Job 没有有效训练变化	可重新打开
SKIPPED_NOT_COMMITTED	当前 Job 主事务未提交	可重新打开
FAILED_NON_BLOCKING	快照处理失败，但同步不受影响	可重试

不能把 SKIPPED_NOT_COMMITTED 设计成永久终态。

原因：

同一 sync_run_id
第一次尝试失败
第二次重试成功

第二次必须能够继续创建快照。

7. 对外结果状态

内部服务返回：

RunnerStateAutoSnapshotResult

结果状态：

CREATED
DUPLICATE_PAYLOAD
SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_NOT_COMMITTED
FAILED_NON_BLOCKING
ALREADY_PROCESSED_TRIGGER
PROCESSING_BY_ANOTHER_WORKER

建议结构：

{
  "status": "CREATED",
  "receipt_id": 21,
  "snapshot_id": 108,
  "trigger_reference": "garmin-sync:cb64dbbf-6a2d-41b8-b697-3d9268b85f48"
}

禁止包含：

完整快照 payload；
Evidence；
Token；
原始 Garmin 数据；
SQL 错误；
堆栈信息。
8. 回执领取

必须使用数据库唯一约束与租约机制，不使用“先查询再插入”冒充并发安全。

8.1 首次处理

尝试插入：

status = PROCESSING
attempt_count = 1
processing_token = 服务端 UUID
locked_at = 当前时间

插入成功后获得处理权。

8.2 唯一冲突

发生唯一约束冲突时，读取已有回执并判断：

已完成
CREATED
DUPLICATE_PAYLOAD

返回：

ALREADY_PROCESSED_TRIGGER

并携带已有 snapshot_id。

正在处理且租约未过期

返回：

PROCESSING_BY_ANOTHER_WORKER

不得再次计算 Runner State。

可重新打开状态

以下状态允许新的 Job 尝试重新领取：

SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_NOT_COMMITTED
FAILED_NON_BLOCKING

重新领取时：

状态改为 PROCESSING；
更新 sync_job_id；
更新 is_committed；
更新 material_change_count；
增加 attempt_count；
生成新的 processing_token；
更新 locked_at；
清空旧错误信息。
9. PROCESSING 租约恢复

防止进程在领取后崩溃，留下永久 PROCESSING。

建议租约：

15分钟

判断：

status = PROCESSING
且 locked_at < 当前时间 - 15分钟
→ 允许重新领取

重新领取必须使用条件 UPDATE，防止两个恢复者同时获得处理权：

UPDATE ...
SET processing_token = :new_token,
    locked_at = :now,
    attempt_count = attempt_count + 1
WHERE id = :receipt_id
  AND status = 'PROCESSING'
  AND locked_at < :expired_before;

只有 rowcount == 1 的执行者获得处理权。

租约时长应集中配置，不散落魔法数字。

10. 自动快照服务

建议新增：

RunnerStateAutoSnapshotService

内部方法：

process_garmin_sync_outcome(
    *,
    user_id: int,
    sync_job_id: int,
    sync_run_id: str,
    committed: bool,
    material_change_count: int,
) -> RunnerStateAutoSnapshotResult

该方法只能由服务器内部调用。

不得增加允许客户端提交以下内容的公共接口：

trigger_type
trigger_reference
snapshot_payload
payload_hash
user_id
11. 服务执行流程
接收 GarminSyncRunOutcome
        ↓
生成 trigger_reference
        ↓
领取或创建触发回执
        ↓
判断 committed/material change
        ↓
计算当前 Runner State
        ↓
创建或复用历史快照
        ↓
完成回执
11.1 未提交
committed = false

结果：

SKIPPED_NOT_COMMITTED

要求：

不计算 Runner State；
不调用快照创建；
回执保持可重新打开；
不产生 snapshot_id。
11.2 没有有效变化
committed = true
material_change_count = 0

结果：

SKIPPED_NO_MATERIAL_CHANGE

要求：

不计算 Runner State；
不调用快照创建；
允许同一 sync_run_id 的后续重试在出现变化后重新处理。
11.3 有有效变化
committed = true
material_change_count > 0

执行当前 Runner State 计算和快照创建。

12. 快照创建事务

快照和回执最终状态必须处于同一个事务。

正确方式：

事务 1
→ 领取 PROCESSING 回执
→ commit

事务 2
→ 计算 Runner State
→ 创建或查询快照
→ 更新回执状态
→ commit

事务 2 中：

创建新快照
snapshot INSERT
receipt.status = CREATED
receipt.snapshot_id = 新快照
receipt.completed_at = 当前时间

同一事务提交。

payload 已存在
读取已存在快照
receipt.status = DUPLICATE_PAYLOAD
receipt.snapshot_id = 已存在快照
receipt.completed_at = 当前时间

同一事务提交。

不能出现：

快照已提交
回执仍然是 PROCESSING
13. 快照服务适配

现有 RunnerStateSnapshotService 需要提供事务友好的内部能力。

建议拆分为：

calculate_snapshot_payload(...)
create_or_get_snapshot_in_transaction(...)

内部方法只允许：

flush()；
捕获预期唯一约束；
返回新建或复用结果。

内部方法不得自行最终 commit()。

公共手动保存接口继续：

调用事务内部方法
→ route/service 外层 commit

必须保持 C2.1 手动保存现有行为和 API 响应不变。

不得复制：

canonical JSON；
SHA-256 哈希；
payload 去重；
Runner State 计算；
快照序列化。
14. 内容去重结果

内部快照结果建议：

RunnerStateSnapshotCreationResult

包含：

snapshot
created
duplicate_reason

duplicate_reason 当前只需要：

PAYLOAD_HASH

自动服务映射：

快照结果	回执结果
created=true	CREATED
created=false	DUPLICATE_PAYLOAD

公共手动保存接口可继续使用原有文案和返回结构，不要求暴露内部原因。

15. 失败处理

自动快照失败不能改变 Garmin 同步结果。

处理流程：

事务 2 异常
→ rollback
→ 使用干净事务重新读取回执
→ 条件更新为 FAILED_NON_BLOCKING
→ 写入安全 error_code
→ commit

失败结果：

FAILED_NON_BLOCKING

允许记录：

receipt ID；
user ID；
sync Job ID；
sync run ID；
-异常类型；
-安全 error code。

禁止记录：

原始 payload；
完整快照；
Evidence；
Garmin Token；
数据库密码；
完整 SQL；
用户邮箱。
16. 防止过期处理者覆盖结果

完成回执时必须校验：

processing_token

更新条件：

UPDATE ...
SET status = :final_status,
    snapshot_id = :snapshot_id,
    completed_at = :now
WHERE id = :receipt_id
  AND status = 'PROCESSING'
  AND processing_token = :processing_token;

只有 rowcount == 1 才能完成。

这可以避免：

Worker A 超时；
Worker B 回收租约并成功处理；
Worker A 迟到后覆盖 Worker B 的结果。

分布式系统里最危险的不是失败，而是一个早该消失的旧进程突然回来宣布自己才是负责人。

17. 重试状态转换

允许转换：

SKIPPED_NOT_COMMITTED
→ PROCESSING
→ CREATED / DUPLICATE_PAYLOAD

SKIPPED_NO_MATERIAL_CHANGE
→ PROCESSING
→ CREATED / DUPLICATE_PAYLOAD

FAILED_NON_BLOCKING
→ PROCESSING
→ CREATED / DUPLICATE_PAYLOAD

终态：

CREATED
DUPLICATE_PAYLOAD

终态不得重新计算。

PROCESSING 只有租约超时才允许恢复。

18. sync_job_id 语义

回执唯一标识按：

sync_run_id

sync_job_id 只记录最近一次处理该回执的具体尝试。

同一个 sync_run_id 可能经历：

Job 101 failed
Job 105 retry succeeded

最终回执：

trigger_reference = garmin-sync:<sync_run_id>
sync_job_id = 105
status = CREATED

不需要保存所有 Job 尝试列表，因为它们已经存在于 external_sync_job 表中。

19. 是否修改快照表

C2.3-B 不给快照表新增：

UNIQUE(user_id, trigger_type, trigger_reference)

原因：

触发幂等由回执表负责；
内容幂等由快照 payload hash 负责；
同一状态可能由多个同步运行触发；
快照记录状态，回执记录事件。

现有快照表结构和哈希规则保持不变。

自动创建的快照仍设置：

trigger_type = GARMIN_SYNC
trigger_reference = garmin-sync:<sync_run_id>

当 payload 重复时，不修改已存在快照的触发字段。

20. API 边界

本阶段不增加公共 API。

现有接口保持：

POST /api/runner-state/snapshots

只允许手动保存，并继续固定：

trigger_type = MANUAL

客户端不得通过现有 API 创建 GARMIN_SYNC 快照。

C2.3-C 再决定如何通过同步任务查询结果返回回执摘要。

21. 迁移设计

新增独立脚本：

scripts/upgrade_v0103_runner_state_snapshot_receipts.py
upgrade
创建回执表；
创建唯一约束；
创建普通索引；
创建外键；
不修改历史快照；
不回填旧 Garmin Job；
不自动生成历史回执。
downgrade
删除回执表；
不删除历史快照；
不修改 ExternalSyncJob；
不修改 Runner State 数据。

同步更新：

sql/schema.sql
scripts/init_db.py
planner_core/database/__init__.py
22. 测试设计
表和迁移
MySQL 5.7 upgrade；
MySQL 5.7 downgrade；
MySQL 8 upgrade；
MySQL 8 downgrade；
同一触发引用唯一；
不同用户可使用相同触发引用；
外键行为正确；
多条手动快照不受影响。
领取与并发
首次创建回执成功；
并发插入只有一个获得处理权；
未过期 PROCESSING 不可重复领取；
过期 PROCESSING 可恢复；
同时恢复只有一个成功；
旧 processing token 不能完成；
attempt_count 正确增加。
状态判断
未提交返回 SKIPPED_NOT_COMMITTED；
无变化返回 SKIPPED_NO_MATERIAL_CHANGE；
两者都不计算 Runner State；
两者都不创建快照；
后续成功重试可重新打开。
快照结果
有变化创建新快照；
一次触发最多一条回执；
一次触发最多一个最终快照结果；
payload 重复映射为 DUPLICATE_PAYLOAD；
重复 payload 回执指向旧快照；
不修改旧快照；
手动保存行为不退化；
current GET 仍不写数据库。
失败隔离
Runner State 计算失败；
序列化失败；
快照 INSERT 失败；
回执最终更新失败；
失败后状态为 FAILED_NON_BLOCKING；
Garmin 同步结果对象不被修改；
失败回执可重新领取；
日志不包含敏感数据。
回归
Runner State A/B/C1/C2 全部通过；
Garmin C2.3-A 全部通过；
完整 pytest 通过；
MySQL 并发测试通过。

所有测试使用虚构用户、虚构训练和 Mock 数据。

23. 文档

新增：

docs/training-knowledge/runner-state-snapshot-trigger-receipt-v1.md

说明：

回执与快照区别；
表结构；
状态机；
两层幂等；
租约；
失败隔离；
重试；
事务边界；
当前限制。

新增：

docs/training-knowledge/runner-state-snapshot-trigger-receipt-learning-notes.md

重点说明：

为什么不能只给快照表加唯一约束；
sync_run_id 和 Job ID 的区别；
为什么跳过状态必须可重新打开；
PROCESSING 租约如何恢复；
processing token 如何防止迟到写入；
快照和回执如何原子提交；
payload 重复如何处理；
如何安全记录失败；
如何扩展其他触发源；
项目负责人验收清单。
24. 开源边界

允许公开：

回执 ORM；
状态机；
内部服务；
迁移脚本；
幂等和并发测试；
虚构测试数据；
技术文档。

保持私有：

真实回执数据；
真实同步结果；
用户训练变化统计；
真实快照案例；
竞赛评测结果。

两个仓库均禁止：

Garmin Token；
API Key；
数据库密码；
原始活动数据；
邮箱；
手机号；
用户身份映射。
25. 验收标准

C2.3-B 完成后必须满足：

回执和快照职责分离；
同一同步运行只有一个回执；
同一触发并发执行只有一个处理者；
未提交不计算快照；
无变化不计算快照；
成功重试可重新打开跳过状态；
快照内容重复不创建新快照；
重复内容仍留下触发回执；
快照与回执最终状态原子提交；
过期 PROCESSING 可恢复；
旧处理者不能覆盖新结果；
失败不修改 Garmin 同步状态；
公共手动 API 不接受 GARMIN_SYNC；
不修改快照哈希；
不修改 Runner State 规则；
MySQL 5.7 和 8 升降级通过；
完整测试通过；
不接入 Pipeline。
26. 实施拆分
1. 回执枚举、ORM 和 Schema
2. 升降级脚本
3. 回执领取服务
4. PROCESSING 租约与 token
5. 事务型快照创建能力
6. 自动快照内部服务
7. 跳过和失败状态
8. 并发测试
9. MySQL 5.7/8 验证
10. 完整回归
11. 文档
27. 设计结论

C2.3-B 建立的是一套内部自动快照处理基础设施。

它不负责决定 Garmin 同步何时调用，只负责保证：

同一个同步事件只被可靠处理一次，状态内容不重复保存，失败不会污染 Garmin 同步主流程。

完成 C2.3-B 后，C2.3-C 只需要在统一 Pipeline 的提交后位置调用该服务，并把回执结果安全地展示给用户。