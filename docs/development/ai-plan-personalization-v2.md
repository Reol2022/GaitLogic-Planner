# AI Plan v2.0 — Personalized Plan Context

## 审计与范围

开发分支 `feat/ai-plan-personalization-v1`，提交父基线 `066f1dc`。原有菜单、后台、MCP、Gilo 等未提交工作留在工作树中，不纳入本轮提交；`scripts/upgrade_v0130_adaptive_plan.py` 不修改、不暂存。

实际调用链仍为 AI Plan API → 原有生成 Service → 一次模型生成 → 结构化校验/约束检查 → AIPlanJob / AIPlanDraft → 人工预览 → 规则引擎 → 正式周期。

审计确认：原生成器只有表单与教练偏好；应用创建了默认 draft 状态周期却跳转“今日”；结构检查未覆盖固定休息、时间、跨周高强度等请求约束。既有 Training Service 完整汇总与截断列表不同，不能用20条列表推导完整基线。既有生命周期启用函数内部提交，直接复用会破坏应用事务。

本轮没有新增Agent、模型、长期记忆、分周生成、设备请求或生产操作。

## Plan Context v2.0

| 字段 | 内容 |
| --- | --- |
| schema_version / as_of_date / timezone | 契约版本、统计截止日、应用时区 |
| runner_facts.training | 完整56日查询聚合，8个滚动7日窗口、最近/此前4周已记录跑量、按日期计算的训练频率、最长单条活动、最多8条关键训练示例 |
| runner_facts.recovery / runner_state | 复用只读 Runner State 的恢复事实、时效、缺口、质量及风险信号 |
| runner_facts.performances | 最多5个已保存配速档案，明确是用户报告而非设备验证比赛成绩 |
| runner_facts.cycle | 当前或最近已完成周期，标记是否当前 |
| runner_facts.last_sync_at / last_sync_status | 最近成功同步时间及最近任务状态，不请求Garmin |
| hard_constraints | 目标距离/成绩/比赛日期、计划日期/周数、训练天数、休息日、每日分钟、双跑、禁用课型 |
| user_reported | 表单中的能力、成绩、跑量、伤病说明；同距离目标差距为服务端基于自述计算，不是成功概率 |
| soft_preferences | 已保存训练哲学、强度风格、长距离偏好日 |
| feasibility / suggestions / fingerprint | 可行性警告或冲突、显式填写候选值、稳定事实指纹 |

来源标记包括 `SERVER_DERIVED_FROM_GAITLOGIC_RECORDS`、`GAITLOGIC_RECOVERY_RECORD`、`USER_REPORTED_SAVED_PROFILE`、`SERVER_DERIVED_FROM_USER_REPORT`。来源为GARMIN的日志也不等于验证过的比赛PB。

约束和上下文保存在现有 `AIPlanJob.input_json`，模型结构化输出保存在既有 `output_json`。草稿详情可查看生成时快照。**不新增数据库字段/表，因此不需要迁移。** 快照是历史上下文，不是最新恢复结论，不进入公开日志、Trace或测试Fixture。

## 事实与缺口

复用 `training_load_service._query_logs` 取得完整56日授权用户日志，复用 `get_recent_training_read(..., limit=0)` 的未关联活动数量，先聚合后截取示例。按稳定活动指纹去重，重复候选、缺失距离及待关联活动显式标记。只有已完成日志参与跑量，不直接把待确认设备活动加入正式训练。

未知周为null，不自动填零；4周均有可用记录才提供平均值。`complete_for_recorded_data` 只描述已记录数据，`sync_coverage_verified=false`，不声明设备同步完整。最长距离为单条活动，不擅自把热身/主课/放松合并。关键训练只使用实际日志分类，不用计划标签冒充实际强度。来源冲突保留提示，不让模型自行补齐数据。

缓存包含事实快照/同步状态/约束，因此相同事实保持原有24小时缓存，事实改变会重新生成。生成失败或草稿保存失败不扣额度；任务、额度、草稿在一次最终提交中完成。

修复了零冷却的时间精度边界：MySQL秒级DATETIME舍入可能使last_generated_at暂时略晚于应用当前时间，原判断会在冷却为0时误限流；现在仅正数冷却执行时间间隔判断，原有正数冷却回归保留。

## 可行性与优先级

安全规则与确定性校验优先；用户硬约束不得被模型或软偏好改变。已保存的禁用课型也继续校验。训练风格、长距离偏好日为软偏好。

阻止调用模型的情况：训练天数与休息日/零分钟日期矛盾、比赛早于计划开始。其余情况给出有限提醒而不是一律拒绝：短准备期、比赛不在本周期、长距离与休息偏好冲突、每周时间较少、未知训练周、恢复过期、同步未完整成功、历史与近期跑量变化、表单与记录不一致、目标提升较大。

35%跑量变化、同距离目标提升10%、120分钟等只是触发确认的产品启发阈值，不是运动处方、成绩达成门槛或科学性证明。不输出成功概率或成绩保证。

输出校验检查起止/比赛日期及目标不变、日期属于对应7日计划周、距离有限且非负、周汇总与明细一致、固定休息日、训练天数上限、同日次数及隐藏双跑文本、禁用课型、每日总分钟、跨周连续高强度。设置时间上限后必须有 `planned_duration_minutes`，不能用缺失时长绕过限制。计划时长保留在原有输出JSON及课程说明中，未引入新正式时长字段。

原有结构Validator与规则引擎继续保留；Prompt不被当作科学性保证。

## 页面与应用事务

- 页面自动读取并展示训练基础；重新获取只更新事实卡片，不覆盖表单。
- 接受跑量需要明确确认；不改变目标、每周天数等硬约束。手动再次修改时展示覆盖来源。
- 支持纯表单入口，生成前可行性检查及警告确认；服务端生成时重新取数并独立检查，不能依赖前端校验。
- 原定时器模拟百分比/阶段已移除，改为诚实的等待状态；尚未实现后台任务轮询。
- 明确区分“仅保存，暂不启用”和“保存并启用”。旧客户端无请求体仍默认仅保存，防止意外激活。
- 规则引擎可先提交审计记录；正式应用前加锁用户/草稿，在同一业务事务中创建周期、训练块、课程和日志，并变更草稿状态；生命周期函数新增默认兼容的 `commit=False` 供该事务使用。
- 不静默结束旧周期。已有active状态周期时拒绝启用并提示先结束旧周期或仅保存；已完成周期日期重叠时阻止启用。草稿被拒绝、重复应用、明细与已校验输出不一致也拒绝。
- 中途失败回滚全部业务写入。前端校验服务端 `cycle_status` / `activated`，成功跳转周期管理查看状态；未来开始的周期不暗示今天已有课表。

## 验收

使用合成数据。隔离MySQL为 `127.0.0.1:3307`、MySQL 8.0.46；仅新建随机 `gaitlogic_test_ai_plan_*` 库，测试完成后删除本轮创建的测试库。没有连接日常或生产数据库。

- 相关后端合并回归：80 passed，0 failed，0 skipped（含16个真实MySQL个性化集成案例、原有额度/缓存MySQL回归及既有生命周期/规则呈现/周复盘输出回归）。既有生命周期测试使用其原有单元夹具，不冒称全部测试均为MySQL。
- 前端：181 passed / 37文件；typecheck、生产build、diff检查通过。构建仍有既有大包及第三方注释警告。
- 浏览器：1440px桌面、390px手机，纯合成API。验证读取不覆盖手填、确认后填入、手改来源、生成前确认、生成预览、启用失败不跳转、仅保存跳到周期管理。
- 真实DB断言涵盖完整/部分/无Garmin来源日志、超过20条聚合、双用户隔离、缓存失效、不扣失败额度、保存/启用状态、已有周期冲突、中途失败回滚、双连接并发应用只创建一个周期、篡改草稿拦截、生成时快照权限。
- 本轮未调用真实LLM或Garmin，不宣称真实模型已能稳定一次生成16周或训练建议质量已获验证。

## 文件与后续边界

后端：`server/schemas/ai_plan.py`、`server/services/ai_plan_context_service.py`、`server/services/ai_plan_constraints.py`、原生成Service/Prompt/API、生命周期Service最小事务扩展。

前端：原AI计划API/页面/类型，新增Plan Context类型及接受值/来源工具；增加工具测试及纯合成浏览器脚本。测试：新增个性化契约与MySQL集成，保留原额度回归并修正旧Fixture与休息日/周跑量自相矛盾的内容。

| 文件 | 本轮修改 |
| --- | --- |
| server/schemas/ai_plan.py | 约束输入、Context响应、草稿快照、应用模式与状态响应 |
| server/services/ai_plan_context_service.py | 训练基础聚合、来源、可行性与稳定指纹 |
| server/services/ai_plan_constraints.py | 确定性硬约束校验 |
| server/services/ai_plan_prompt.py | 单次生成使用统一Context，保留原Prompt接口兼容 |
| server/services/ai_plan_service.py | Context接入、缓存/失败额度、原子应用、零冷却修复 |
| server/services/training_cycle_lifecycle_service.py | 可由调用方控制最终提交，默认行为不变 |
| server/api/routes/ai_plan.py | 认证Context API、历史快照、明确应用模式 |
| web/src/api/aiPlan.ts | 新增Context调用与应用请求体 |
| web/src/types/models.ts | 约束字段及草稿Context类型 |
| web/src/types/planContext.ts | 页面使用的Context类型 |
| web/src/utils/planContext.ts | 自动填写允许字段、来源提示 |
| web/src/utils/planContext.test.ts | 手动覆盖、非法候选值回归 |
| web/src/views/AIPlanGenerator.vue | 事实展示、显式接受、约束填写、检查确认、两种应用模式 |
| tests/test_ai_plan_personalization.py | 合成聚合、目标检查和硬约束测试 |
| tests/test_ai_plan_personalization_mysql.py | 隔离MySQL事实、缓存、事务、并发和API验收 |
| tests/test_ai_plan_quota.py | 保留原回归，修正合成Fixture矛盾并禁止连接非本机MySQL |
| tools/ai_plan_context_smoke.cjs | 桌面/手机合成浏览器验收 |
| docs/development/ai-plan-personalization-v2.md | 审计、契约、测试及限制说明 |

已知限制：同步接口仍为单次模型生成，长计划可能超时/截断；无真实Provider质量验收；单活动不等于整堂长距离；未知周可能导致没有自动填写候选值；原有并发额度预留机制没有在本轮重构；正式计划没有独立分钟字段。未为MCP、Coach Assessment等实验代码新增依赖。

下一阶段Weekly Blueprint建议：先固定周目标/负荷与约束，再分周生成并逐周校验；为长任务增加幂等任务状态与可恢复执行。这里只记录建议，本轮不实现。

没有合并master、推送、执行生产迁移或部署。
