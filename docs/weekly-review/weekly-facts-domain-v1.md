# Weekly Facts Domain v1

## 目标

Weekly Facts 是 v0.13.0 的只读、确定性周训练事实层。它把既有
`TrainingCycle`、`TrainingBlock`、`PlannedWorkout`、`WorkoutLog` 和
Runner State 历史快照转换为严格 Schema；不生成自然语言、不调用模型、
不写数据库，也不修改课表。

当前版本：

- `weekly-facts-1.0.0`
- `weekly-review-rules-1.0.0`

## 输入与时间边界

请求包含服务端可信的 `user_id`、周起止日期、可选周期 ID 和 IANA 时区。
窗口最多七个自然日。计算以业务时区的 `as_of_date` 截断，周内未来计划既
不算完成，也不算缺课。公开 API 尚未在 A 阶段提供，未来 API 必须由认证
上下文注入用户 ID。

## 数据流

```text
ORM facts
  -> WeeklyFactsService (only SELECT)
  -> normalized domain inputs
  -> build_weekly_facts (pure aggregation)
  -> WeeklyFacts + stable SHA-256
```
SQL 只存在于服务适配层。领域聚合只接收 Pydantic 对象，因此可以脱离
数据库重复测试。

## 输出结构

- `period`：周期、时区、训练周期和训练阶段引用。
- `planned`：计划次数、跑量、时长、关键课、长距离和休息日。
- `completed`：实际完成次数、跑量、时长、关键课、长距离和实际休息日。
- `adherence`：次数、距离、关键课和长距离完成率。
- `distribution`：easy、moderate、hard 和 unknown 的距离与比例。
- `deviations`：结构化偏差、证据码、预期值与实际值。
- `runner_state_trend`：窗口首尾状态与变化；不足两条时为 `UNKNOWN`。
- `data_quality`：完整度、缺失字段、未匹配和歧义数量。
- `classification`：确定性主状态、次状态、规则码、警告和限制。
- `result_hash`：排除生成时间后的规范化 JSON SHA-256。

## 匹配与去重

优先使用 `planned_workout_id`。没有显式关联时，只在同日且训练主类型兼容、
候选唯一时匹配。多个候选不会猜测，记录为歧义。没有候选的日志保留为
unmatched/extra。相同非空 `activity_fingerprint` 只统计一次并记录重复偏差。
取消计划不进入分母。

## 单位和缺失值

距离统一为公里，时长统一为分钟，输出保留两位小数；比例保留四位。
缺失距离或时长不转换为真实零。分母为零时返回 `null`，不会产生 NaN 或
Infinity。力量训练计入训练次数和总时长，但不进入跑步距离。

## 安全边界

输出不含邮箱、手机号、Garmin Token、API Key、GPS 轨迹、原始 Provider
响应或完整训练正文。测试数据和示例均为虚构。A 阶段没有 API、前端、迁移、
持久化周报或 Agent 接入。

## 虚构示例

```json
{
  "period": {
    "week_start": "2026-01-05",
    "week_end": "2026-01-11",
    "timezone": "Asia/Shanghai",
    "cycle_id": 9001,
    "cycle_name": "虚构春季基础周期",
    "training_phase": "BASE"
  },
  "planned": {"planned_running_session_count": 4, "planned_distance_km": 32.0},
  "completed": {"completed_running_session_count": 3, "actual_distance_km": 25.0},
  "classification": {
    "primary_status": "UNDER_COMPLETED",
    "secondary_statuses": [],
    "rule_codes": ["DISTANCE_COMPLETION_BELOW_0_80"],
    "warnings": [],
    "limitations": ["PLANNED_DURATION_NOT_STRUCTURED"]
  }
}
```
