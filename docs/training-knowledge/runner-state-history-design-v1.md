# 跑者状态历史快照设计 v1

> 对应版本：GaitLogic v0.10.3-C2  
> 文档状态：设计草案  
> 快照结构版本：`runner-state-snapshot-1.0.0`  
> 前置版本：
>
> - v0.10.3-A Runner State Foundation
> - v0.10.3-B Runner State Inference Rules
> - v0.10.3-C1 Current Runner State Presentation

---

## 1. 设计背景

当前系统能够通过：

```text
GET /api/runner-state/current

实时计算跑者状态。

当前状态会根据最新训练日志、训练计划和规则配置变化，因此它只能回答：

跑者现在的状态是什么？

它无法回答：

一周前的状态是什么；
疲劳信号何时开始增加；
跑量突增后状态如何变化；
某次训练调整之前，系统依据了什么；
当时使用的是哪一版规则；
当前结果和历史结果为什么不同。

因此需要建立不可变的历史快照，用于保存特定时刻的状态结果及其判断依据。

2. 版本目标

本版本实现：

保存当前跑者状态快照；
防止相同状态重复保存；
保存当时使用的规则版本；
保存基础指标和完整推断结果；
查询历史快照列表；
查询单个历史快照详情；
保证用户只能访问自己的快照；
支持后续历史趋势展示；
支持后续 Garmin 同步触发快照；
支持后续训练动态调整审计。

本版本不实现：

状态重新训练；
历史快照修改；
自动修改训练计划；
医疗诊断；
历史竞技能力预测；
每日定时任务；
用户之间的状态比较；
公开排行榜。
3. 核心概念
3.1 当前状态

当前状态由实时数据计算得出：

训练日志 + 训练计划 + 当前规则配置
→ RunnerStateSnapshot

特点：

实时计算；
不写数据库；
会随训练数据变化；
会随规则版本变化。
3.2 历史快照

历史快照是某次计算结果的不可变记录。

特点：

创建后不修改；
保留当时的基础指标；
保留当时的推断结果；
保留当时的 Evidence；
保留当时的规则版本；
不随当前训练数据重新计算。
3.3 设计原则
GET 当前状态
→ 只读，不创建快照

POST 保存快照
→ 重新计算当前状态并保存

GET 历史快照
→ 读取当时保存的结果，不重新计算
4. 实施阶段
C2.1 快照后端基础

实现：

数据库模型；
数据库迁移；
快照序列化；
稳定哈希；
手动保存；
重复检测；
列表查询；
详情查询；
权限测试。
C2.2 历史展示

实现：

当前状态与历史趋势切换；
历史快照列表；
跑量趋势；
状态时间线；
风险标记时间线；
快照详情；
移动端展示。
C2.3 Garmin 自动触发

实现：

Garmin 同步成功后触发；
仅数据实际变化时保存；
同一次同步不重复创建；
同一状态不重复保存。

C2.1 阶段只实现手动保存，不接入 Garmin 同步流程。

5. 数据模型

建议数据库模型名称：

RunnerStateSnapshotRecord

不要与现有 Pydantic Schema：

RunnerStateSnapshot

使用完全相同的名称，避免 ORM 模型和接口模型混淆。

6. 建议字段
6.1 标识字段
id
user_id
snapshot_date
data_cutoff_date
calculated_at
created_at
trigger_type
trigger_reference

含义：

字段	含义
id	快照主键
user_id	所属用户
snapshot_date	快照所属业务日期
data_cutoff_date	状态计算的数据截止日期
calculated_at	状态实际计算时间
created_at	快照写入数据库时间
trigger_type	创建触发方式
trigger_reference	可选的内部触发标识

snapshot_date 和 data_cutoff_date 第一版通常相同，但保留两个字段，避免后续补录历史快照时失去表达能力。

6.2 版本字段
snapshot_schema_version
ruleset_version

示例：

snapshot_schema_version = runner-state-snapshot-1.0.0
ruleset_version = runner-state-rules-1.0.0

历史快照必须保留当时使用的规则版本。

以后规则升级后，旧快照不得重新套用新规则。

6.3 常用查询字段

为了避免历史列表每次解析整个 JSON，以下字段单独存储：

distance_7d_km
distance_28d_km
volume_trend
training_consistency
fatigue_state
training_phase
risk_flag_count
evidence_coverage
data_completeness

这些字段用于：

历史列表；
趋势图；
状态筛选；
统计查询。

字段允许为空。

缺失值不得写成 0。

6.4 完整快照字段
snapshot_payload
payload_hash

snapshot_payload 使用数据库 JSON 类型，保存完整状态结果：

基础指标；
派生指标；
状态推断；
-风险标记；
Evidence；
skipped signals；
data quality；
limitations；
inference metadata。

不得保存：

用户邮箱；
手机号；
密码；
Garmin Token；
API Key；
数据库连接信息；
完整原始训练日志；
ExternalActivity 原始响应；
用户身份映射。
7. 建议 ORM 结构

概念结构如下，实际代码遵循项目现有 SQLAlchemy 风格：

class RunnerStateSnapshotRecord:
    id: int
    user_id: int

    snapshot_date: date
    data_cutoff_date: date
    calculated_at: datetime
    created_at: datetime

    trigger_type: str
    trigger_reference: str | None

    snapshot_schema_version: str
    ruleset_version: str
    payload_hash: str

    distance_7d_km: Decimal | None
    distance_28d_km: Decimal | None
    volume_trend: str
    training_consistency: str
    fatigue_state: str
    training_phase: str
    risk_flag_count: int
    evidence_coverage: Decimal | None
    data_completeness: Decimal | None

    snapshot_payload: dict
8. 触发类型

定义：

MANUAL
GARMIN_SYNC
DAILY
PLAN_ADJUSTMENT
SYSTEM
C2.1 启用
MANUAL
C2.1 暂不启用
GARMIN_SYNC
DAILY
PLAN_ADJUSTMENT
SYSTEM

公共手动保存接口不接受客户端传入任意 trigger_type。

用户调用保存接口时，后端固定：

trigger_type = MANUAL

避免客户端伪造系统或 Garmin 触发记录。

9. 时区与日期语义

状态日期必须以后端当前业务时区为准。

当前项目使用：

Asia/Shanghai

要求：

snapshot_date 由后端计算；
前端不得根据浏览器本地时区自行生成；
data_cutoff_date 直接取状态快照中的截止日期；
API 时间使用带时区的 ISO 8601 表达；
数据库存储方式遵循项目现有时间字段约定；
跨日边界必须测试。

即使用户浏览器位于东京，也不能让同一训练状态突然“穿越”到另一天。

10. 快照哈希
10.1 目的

payload_hash 用于判断：

当前状态与最近保存的状态是否完全相同。

哈希算法建议：

SHA-256
10.2 规范化过程

在计算哈希前：

将快照转换为普通字典；
移除非语义时间字段；
对字典键进行稳定排序；
使用固定 JSON 编码；
统一小数和枚举序列化；
对规范化 JSON 计算 SHA-256。
10.3 不参与哈希的字段

以下字段不参与哈希：

calculated_at
created_at

否则每次点击保存都会因为时间不同产生新记录，去重功能会当场下班。

10.4 参与哈希的字段

必须参与：

data cutoff date；
基础指标；
派生指标；
状态推断；
-风险标记；
Evidence；
data quality；
limitations；
ruleset version；
snapshot schema version。
10.5 稳定性要求

以下情况必须生成相同哈希：

JSON 键顺序不同；
字典构造顺序不同；
calculated_at 不同；
created_at 不同。

以下情况必须生成不同哈希：

跑量变化；
状态变化；
-风险标记变化；
Evidence 变化；
data quality 变化；
ruleset version 变化；
snapshot schema version 变化；
data cutoff date 变化。
11. 重复快照策略

用户明确保存时，后端执行：

1. 实时计算当前状态
2. 生成规范化 payload
3. 计算 payload_hash
4. 查询当前用户同一 data_cutoff_date 的相同 hash
5. 存在则返回已有快照
6. 不存在则创建新快照

API 返回：

{
  "snapshot": {},
  "created": false,
  "duplicate": true
}

或者：

{
  "snapshot": {},
  "created": true,
  "duplicate": false
}

连续点击保存不能生成一排克隆快照。

12. 并发去重

只在服务层先查询不足以防止并发重复。

需要数据库唯一约束：

user_id
data_cutoff_date
payload_hash

建议唯一索引：

uq_runner_state_snapshot_user_cutoff_hash

保存时：

先进行应用层重复检查；
尝试插入；
捕获唯一约束冲突；
查询并返回已存在记录；
不向用户返回 500。

这样即使用户双击、两个请求同时到达，也只会留下一个快照。

13. 索引设计

建议：

INDEX(user_id, data_cutoff_date)
INDEX(user_id, created_at)
UNIQUE(user_id, data_cutoff_date, payload_hash)

查询历史列表时始终包含 user_id。

不建立跨用户状态排行榜索引。

14. 快照不可变原则

快照创建后：

不提供更新接口；
不重新计算；
不覆盖旧 payload；
不修改 ruleset version；
不修改 Evidence。

第一版不提供：

PUT /api/runner-state/snapshots/{id}
PATCH /api/runner-state/snapshots/{id}

未来规则升级后，新状态创建新快照。

旧快照继续表示当时的判断。

15. API 设计
15.1 当前状态

保留：

GET /api/runner-state/current

要求：

只读；
不创建快照；
不写数据库；
返回最新实时计算结果。
15.2 手动保存快照

新增：

POST /api/runner-state/snapshots

请求体第一版为空，或只接受明确的客户端请求 ID。

不得接受：

user_id
trigger_type
ruleset_version
snapshot_payload
payload_hash

这些全部由后端生成。

处理流程：

当前认证用户
→ 计算当前状态
→ 创建或复用历史快照
→ 返回结果
15.3 历史快照列表

新增：

GET /api/runner-state/snapshots

查询参数：

start_date
end_date
limit
offset 或 cursor

分页方式优先复用项目现有规范。

建议：

default limit = 30
maximum limit = 100

默认排序：

data_cutoff_date DESC
created_at DESC

列表默认只返回摘要字段，不返回完整 snapshot_payload。

15.4 历史快照详情

新增：

GET /api/runner-state/snapshots/{snapshot_id}

返回：

快照摘要字段；
完整 snapshot payload；
trigger type；
ruleset version；
schema version；
calculated at；
created at。

只能读取当前用户自己的快照。

其他用户的快照统一返回项目现有的 404 或权限响应，不泄露记录是否存在。

16. 历史列表同日记录策略

同一用户、同一日期可能出现多个不同快照：

上午保存
→ 状态 A

晚上完成训练后保存
→ 状态 B

两条记录都保留。

历史趋势页面默认展示：

每个 data cutoff date 最后一条快照。

历史详情列表可查看该日期的其他版本。

C2.1 的后端列表接口先返回所有快照。

C2.2 展示层再决定是否按日期折叠。

17. 删除策略

C2.1 不提供单条快照删除接口。

原因：

快照用于状态追溯；
单条删除会破坏历史连续性；
当前没有明确产品需求。

但必须满足：

用户账号删除
→ 关联快照一起删除

采用符合项目现有用户数据生命周期的外键或清理机制。

未来可增加：

清除全部训练状态历史

但必须由用户明确确认。

18. 快照服务

建议新增：

RunnerStateSnapshotService

职责：

调用现有 RunnerStateService；
获取实时 RunnerStateSnapshot；
转换为持久化 payload；
规范化 payload；
计算 hash；
检查重复；
创建快照；
处理并发唯一约束；
查询列表；
查询详情；
转换 API Schema。

不得：

重新实现状态推断；
重复查询完整训练数据；
修改训练计划；
调用大语言模型；
修改历史快照。
19. 数据流
保存流程
POST /api/runner-state/snapshots
        ↓
认证当前用户
        ↓
RunnerStateService
        ↓
RunnerStateInferenceService
        ↓
当前 RunnerStateSnapshot
        ↓
Snapshot Serializer
        ↓
Canonical JSON
        ↓
SHA-256
        ↓
重复检查与数据库唯一约束
        ↓
RunnerStateSnapshotRecord
查询流程
GET /api/runner-state/snapshots
        ↓
按当前用户查询摘要字段
        ↓
返回历史列表
GET /api/runner-state/snapshots/{id}
        ↓
按 id + 当前 user_id 查询
        ↓
直接返回保存 payload
        ↓
不重新运行状态推断
20. 数据迁移

C2.1 需要新增数据库迁移。

迁移必须包含：

快照表；
外键；
JSON 字段；
唯一约束；
普通索引；
完整 downgrade。

迁移不得：

修改训练日志表；
修改 Garmin 表；
修改计划表；
回填真实用户状态；
自动创建历史记录；
扫描并复制生产训练数据。

迁移完成后数据库为空表是正常结果。

21. API Schema

建议新增：

RunnerStateSnapshotRecordRead
RunnerStateSnapshotListItem
RunnerStateSnapshotCreateResult
RunnerStateSnapshotListResponse

列表项只包含摘要字段。

详情响应包含完整 payload。

不返回：

user_id
payload_hash
内部数据库外键

payload_hash 可保留在服务器内部，不必暴露给普通用户。

22. 错误处理

需要明确处理：

当前状态无法计算

返回现有状态服务对应错误。

不得保存半成品快照。

数据库插入失败

事务回滚，返回明确错误。

并发重复

返回已存在快照，不返回 500。

快照不存在

返回 404。

越权访问

不泄露其他用户记录。

JSON 序列化失败

明确记录结构化错误，但日志不得输出完整用户快照。

23. 日志设计

允许记录：

快照 ID；
用户内部 ID；
trigger type；
ruleset version；
是否创建；
是否重复；
错误类型。

不得记录：

完整 snapshot payload；
完整 Evidence；
Garmin Token；
用户邮箱；
手机号；
原始训练日志。
24. 测试设计
模型与迁移
表可以创建；
downgrade 可以删除；
唯一约束正确；
JSON 字段正确；
用户删除时关联记录正确处理。
哈希
相同 payload 生成相同 hash；
JSON 键顺序不影响 hash；
calculated_at 不影响 hash；
created_at 不影响 hash；
指标变化会改变 hash；
Evidence 变化会改变 hash；
ruleset version 变化会改变 hash；
data cutoff date 变化会改变 hash。
保存服务
第一次保存创建记录；
相同状态再次保存返回已有记录；
状态变化后创建新记录；
同日不同状态允许保存；
并发重复只产生一条；
保存失败正确回滚；
不修改训练计划；
不调用大语言模型。
API
未登录不能保存；
登录用户可以保存；
请求体不能伪造 user_id；
请求体不能伪造 trigger type；
列表只返回当前用户数据；
详情只返回当前用户数据；
其他用户访问返回 404 或项目统一权限响应；
GET current 不写数据库；
列表支持日期范围；
分页限制有效；
列表不返回完整 payload；
详情返回保存时的 payload；
详情不会重新计算状态；
API 不暴露敏感字段。

所有测试使用虚构数据。

25. C2.2 历史展示预留

C2.2 在现有：

/runner-state

增加：

当前状态
历史趋势

两个页面区域或标签页。

历史趋势至少展示：

最近 28 天；
最近 12 周；
最近 6 个月；
7 天跑量趋势；
28 天跑量趋势；
fatigue state 时间线；
training consistency 时间线；
-风险标记时间线；
数据质量变化；
规则版本变化。

分类状态不建议画成连续数值曲线。

应使用：

状态时间线；
分段标签；
日历标记；
事件节点。
26. Garmin 自动快照预留

C2.3 才接入 Garmin。

触发条件：

Garmin 同步成功
且 WorkoutLog 数据发生有效变化
且当前状态与最近快照不同
→ 创建 GARMIN_SYNC 快照

不得在以下情况保存：

同步失败；
没有新增或更新训练日志；
仅同步任务状态变化；
状态 payload 完全相同；
同一个同步任务重复回调。

C2.1 不修改 Garmin 同步服务。

27. 隐私与安全

快照属于用户私有训练数据。

要求：

所有查询必须附带当前 user_id；
URL 不接受用户 ID；
不在日志打印完整 payload；
不保存凭据；
不保存真实身份字段；
竞赛数据必须另行脱敏；
公开仓库只保存 Schema、代码和虚构测试；
用户删除时清除历史快照；
历史快照不得用于未经授权的公开比较。
28. 开源边界
允许公开
ORM 模型；
数据库迁移；
快照服务；
哈希算法；
API；
权限测试；
虚构测试数据；
历史展示组件；
技术文档。
保持私有
真实用户快照；
内测状态分布；
竞赛评测结果；
用户状态变化案例；
真实截图；
私有调参结果。
两个仓库都禁止
Garmin Token；
API Key；
数据库密码；
数据库备份；
未脱敏训练记录；
手机号；
邮箱；
用户身份映射。
29. 验收标准

C2.1 完成后必须满足：

GET current 仍然不写数据库；
POST snapshots 可以保存当前状态；
客户端不能提交 snapshot payload；
客户端不能伪造 trigger type；
相同状态不会重复保存；
并发请求不会生成重复记录；
状态变化后可以创建新记录；
快照创建后不可修改；
历史详情不会重新计算；
旧快照保留旧 ruleset version；
列表只返回摘要；
详情返回完整 payload；
用户只能读取自己的记录；
不暴露 user_id 和 payload_hash；
用户删除时清理快照；
不调用大语言模型；
不修改训练计划；
不接入 Garmin 同步；
不实现历史前端页面；
数据库迁移可以升级和回滚。
30. 设计结论

历史快照不是训练日志的副本，也不是每天机械复制一份 JSON。

它保存的是：

某一时刻，系统基于当时的数据和规则得出的可解释训练状态结论。

快照必须同时具备：

不可变；
可追溯；
可去重；
有版本；
有权限；
可回滚迁移；
不包含敏感身份信息。

C2.1 只负责把历史状态可靠地保存和读取。

趋势图、Garmin 自动触发和动态训练调整，应建立在快照基础稳定之后。


## 本阶段确定的实施边界

| 内容 | C2.1 |
|---|---|
| 快照表与迁移 | 实现 |
| 手动保存 API | 实现 |
| 历史列表 API | 实现 |
| 历史详情 API | 实现 |
| 稳定哈希与去重 | 实现 |
| 并发唯一约束 | 实现 |
| 当前状态 GET 写库 | 禁止 |
| 历史前端页面 | 暂不实现 |
| Garmin 自动快照 | 暂不实现 |
| 每日定时快照 | 暂不实现 |
| 删除单条快照 | 暂不实现 |
| 自动调整训练计划 | 禁止 |

先按这份设计确认 C2.1 的表结构、哈希范围与接口边界，随后再进入 Codex 实现命令。📚🏃‍♂️