Garmin 同步后自动状态快照设计 v1

对应版本：GaitLogic v0.10.3-C2.3
文档状态：设计确认稿
前置版本：

v0.10.3-C2.1 历史状态快照
v0.10.3-C2.2 历史趋势与详情展示
1. 设计目标

Garmin 同步完成并对训练事实产生实际影响后，系统自动保存一条跑者状态快照。

核心链路：

Garmin 同步成功
    ↓
WorkoutLog 发生有效变化
    ↓
同步事务成功提交
    ↓
重新计算当前跑者状态
    ↓
创建 GARMIN_SYNC 快照

自动快照用于让状态历史自然形成，避免用户每天手动点击“保存今日状态”。

本阶段不实现：

同步前后状态对比解释；
自动调整训练计划；
每日定时快照；
失败同步快照；
每条 Garmin 活动单独创建快照；
大语言模型总结；
前端新的历史页面。
2. 核心原则
2.1 一次同步最多生成一条快照

Garmin 同步可能导入多条活动，但自动快照必须在整次同步完成后统一创建。

禁止：

每同步一条活动
→ 创建一次快照

正确方式：

整次同步完成
→ 汇总实际变化
→ 最多创建一次快照

否则跑者晨跑同步十个分段，数据库就会收到十张几乎一样的纪念照。

2.2 只有训练事实变化才触发

只有影响 Runner State 计算的数据发生变化时，才允许创建自动快照。

2.3 快照失败不能拖垮同步

Garmin 数据同步是主流程，状态快照是后置增强能力。

必须满足：

同步成功 + 快照失败
→ Garmin 同步仍然成功

快照失败只能产生：

结构化警告；
可观测日志；
自动快照结果为失败。

不得回滚已经成功提交的训练数据。

3. 有效变化定义

建议新增统一结果字段：

runner_state_affecting_change_count

只有该值大于 0 时才触发自动快照。

3.1 属于有效变化

以下变化可能影响 Runner State：

新建规范化 WorkoutLog；
已有日志的训练日期改变；
训练状态改变；
主训练类型改变；
距离改变；
时长改变；
平均心率改变；
Garmin 活动与训练日志的关联发生变化，并影响去重或统计；
原本未完成的训练变为完成；
原本无效的训练记录变为有效。
3.2 不属于有效变化

以下情况不触发：

仅更新同步时间；
仅更新同步游标；
仅更新任务状态；
拉取到的数据与现有数据完全相同；
外部原始 JSON 变化，但规范化训练日志未变化；
重试同一同步任务但未产生新训练事实；
同步失败并回滚；
只修改日志信息字段但不影响 Runner State；
只刷新 Garmin Token。
3.3 不能仅依赖导入条数

以下判断不可靠：

fetched_activity_count > 0

因为“拉取到活动”不等于“训练状态数据发生变化”。

必须由同步服务明确返回：

{
  "created_logs": 2,
  "updated_logs": 1,
  "unchanged_activities": 6,
  "runner_state_affecting_change_count": 3
}
4. 触发时机

自动快照必须在以下步骤之后执行：

1. Garmin 活动拉取完成
2. 活动规范化完成
3. 重复检测完成
4. 复合活动合并完成
5. WorkoutLog 创建或更新完成
6. 数据库事务成功提交
7. 自动状态快照

不能在训练数据事务提交之前创建快照。

否则快照服务可能：

看不到刚同步的数据；
保存旧状态；
因后续同步回滚而留下幽灵快照。
5. 事务边界

建议使用两个独立事务：

事务 A：Garmin 同步和 WorkoutLog 更新
提交成功
    ↓
事务 B：Runner State 快照创建
快照事务成功

正常返回：

snapshot_status = CREATED
快照状态重复

正常返回：

snapshot_status = DUPLICATE
快照失败

Garmin 同步仍成功：

sync_status = SUCCESS
snapshot_status = FAILED

同时记录不包含敏感信息的错误日志。

不得：

因快照失败将同步任务改为失败；
回滚训练日志；
自动重跑整个 Garmin 同步；
向用户返回模糊的 500。
6. 触发引用

使用 C2.1 已有字段：

trigger_type
trigger_reference

自动快照固定：

trigger_type = GARMIN_SYNC

trigger_reference 使用稳定的同步任务标识：

garmin-sync:<sync_run_id>

示例：

garmin-sync:8f5d2a31

要求：

同一次同步的所有重试使用同一个 sync_run_id；
不包含 Garmin Token；
不包含邮箱、手机号；
不包含完整外部活动数据；
长度不超过现有 128 字符限制；
不能每次重试随机生成新标识。

如果现有同步流程没有稳定的同步任务 ID，应先增加同步运行上下文，而不是用当前时间随手拼一个。时间戳不是幂等键，只是人类把重复问题推迟几毫秒的传统艺术。

7. 双重幂等策略

自动快照需要两层去重。

7.1 同步任务幂等

保存前查询：

user_id
+ trigger_type = GARMIN_SYNC
+ trigger_reference

若已经存在：

ALREADY_PROCESSED_TRIGGER

不重新计算或创建。

这样可以防止同一同步任务被重复回调。

7.2 状态内容去重

继续复用 C2.1：

user_id
+ data_cutoff_date
+ payload_hash

即使不同同步任务最终产生完全相同状态，也不重复保存。

可能出现：

同步任务 A
→ 状态未变化
→ DUPLICATE_PAYLOAD
7.3 是否新增数据库唯一约束

推荐增加：

UNIQUE(user_id, trigger_type, trigger_reference)

MySQL 对可空唯一字段允许多条 NULL，因此不会影响普通手动快照。

这样可以防止并发或任务重放产生相同触发引用的多条记录。

这意味着 C2.3 需要一份小型数据库升级脚本，只新增唯一约束，不修改已有数据语义。

迁移前必须检查是否存在重复的非空 trigger_reference。若存在，应停止迁移并报告，不能偷偷删除数据。

8. 自动快照结果

建议定义：

RunnerStateAutoSnapshotStatus

状态包括：

CREATED
DUPLICATE_PAYLOAD
ALREADY_PROCESSED_TRIGGER
SKIPPED_NO_MATERIAL_CHANGE
SKIPPED_SYNC_NOT_COMMITTED
FAILED_NON_BLOCKING

同步结果可以增加：

{
  "sync_status": "SUCCESS",
  "runner_state_snapshot": {
    "status": "CREATED",
    "snapshot_id": 123
  }
}

失败时：

{
  "sync_status": "SUCCESS",
  "runner_state_snapshot": {
    "status": "FAILED_NON_BLOCKING",
    "snapshot_id": null
  }
}

不要将完整异常、payload 或数据库信息返回前端。

9. 快照服务扩展

现有：

RunnerStateSnapshotService

建议增加内部方法：

create_snapshot_after_garmin_sync(
    user_id,
    sync_run_id,
    material_change_count,
)

职责：

校验变化数量；
生成稳定 trigger reference；
检查同步任务是否已处理；
调用现有快照创建流程；
固定 GARMIN_SYNC 触发类型；
返回自动快照结果；
隔离异常。

不得：

重新实现快照哈希；
重新实现状态推断；
接受客户端传入 payload；
接受客户端传入任意 trigger type；
修改历史快照。
10. Garmin 同步结果契约

Garmin 同步服务需要明确输出：

{
  "sync_run_id": "8f5d2a31",
  "committed": true,
  "created_log_count": 2,
  "updated_log_count": 1,
  "unchanged_count": 5,
  "runner_state_affecting_change_count": 3
}

不允许调用层通过模糊条件猜测：

created + updated > 0

因为某些 update 可能只是无关字段变化。

同步层负责回答：

是否发生了影响跑者状态的训练事实变化？

快照层负责回答：

根据最新训练事实，是否需要保存新的状态快照？

两层职责不能混成一团。

11. 部分成功处理

如果现有同步支持部分成功，只有同时满足以下条件才允许创建快照：

至少一项训练事实成功提交
且
runner_state_affecting_change_count > 0

例如：

8条活动成功
1条活动解析失败
成功数据已经提交
→ 可以创建快照

但必须在同步结果中保留 warning。

如果整次事务回滚：

committed = false
→ 不创建快照
12. 日志设计

允许记录：

内部用户 ID；
sync run ID；
trigger reference；
material change count；
snapshot ID；
自动快照状态；
异常类型。

不得记录：

Garmin Token；
用户邮箱；
手机号；
原始活动 JSON；
完整状态 payload；
完整 Evidence；
数据库密码。

建议日志示例：

Garmin sync auto snapshot completed:
user_id=12
sync_run_id=8f5d2a31
status=CREATED
snapshot_id=123
13. 前端范围

C2.3 不新增主页面。

已有历史页面已支持：

GARMIN_SYNC -> Garmin同步

因此自动生成的快照会自然出现在：

历史趋势；
快照列表；
快照详情；
触发方式展示。

可选地在 Garmin 同步结果中显示：

训练数据已同步，训练状态历史已更新

但自动快照失败时，不应显示同步失败。

14. 测试设计
触发条件
同步成功且有有效变化，创建快照；
同步成功但无变化，不创建；
同步失败，不创建；
事务回滚，不创建；
只有同步元数据变化，不创建；
多条活动只创建一条快照；
部分成功且有效数据已提交，创建一条。
幂等
同一 sync run 重试不重复创建；
同一 trigger reference 并发调用只创建一条；
不同 sync run、相同状态使用 payload 去重；
不同 sync run、状态变化后创建新快照；
同步回调重复执行不产生额外记录。
失败隔离
快照状态计算失败，同步仍成功；
快照数据库失败，同步仍成功；
快照序列化失败，同步仍成功；
快照失败后训练日志仍存在；
快照失败记录结构化警告；
不泄露异常敏感信息。
权限和边界
快照只能属于当前同步用户；
客户端不能伪造 trigger type；
客户端不能伪造 trigger reference；
不修改训练计划；
不调用大语言模型；
GET current 仍不写数据库；
手动保存行为不退化；
历史 Timeline 正常显示 Garmin 快照。
MySQL 8
新唯一约束 upgrade 通过；
downgrade 通过；
重复 trigger reference 被数据库拒绝；
多条 NULL trigger reference 不冲突；
并发幂等测试通过。
15. 验收标准

C2.3 完成后必须满足：

同步成功且训练事实变化才创建快照；
一次同步最多创建一条；
无变化不创建；
同步失败不创建；
同步事务提交后才创建；
快照失败不影响同步结果；
使用 GARMIN_SYNC；
使用稳定 trigger reference；
同一同步任务可幂等重放；
相同状态继续使用 payload 哈希去重；
自动快照出现在历史页面；
不新增独立历史页面；
不调用大语言模型；
不自动调整训练计划；
不记录敏感数据；
MySQL 8 迁移可升级和回滚；
完整测试通过。
16. 实施顺序
1. 调查现有 Garmin 同步完整调用链
2. 确认是否存在稳定 sync_run_id
3. 列出 Runner State 实际依赖字段
4. 建立 material change 结果契约
5. 设计 trigger reference
6. 增加触发引用唯一约束
7. 扩展快照服务
8. 在同步提交后接入自动快照
9. 实现失败隔离
10. 补充同步结果字段
11. 测试幂等、并发和回滚
12. MySQL 8 upgrade/downgrade
13. 完整回归
14. 更新文档
当前确定的实现决策
项目	决策
自动触发时机	整次同步事务提交后
单次同步快照数	最多一条
有效变化判断	同步服务明确返回
触发类型	GARMIN_SYNC
触发引用	garmin-sync:<sync_run_id>
同一任务重试	不重复创建
相同状态	继续使用 payload hash 去重
快照失败	不影响 Garmin 同步成功
前端新页面	不增加
历史页面	自动兼容 Garmin 快照
是否新增约束	增加 trigger reference 唯一约束
是否修改训练计划	禁止
是否调用大模型	禁止