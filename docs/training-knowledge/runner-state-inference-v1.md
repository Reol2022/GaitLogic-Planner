# Runner State Inference v1

## 目标与边界

v0.10.3-B 在 Runner State Foundation 的按需快照上增加可追溯的确定性启发式推断。它不调用大语言模型、不持久化快照、不生成或调整训练计划，也不提供医疗诊断。相同输入、规则集和计算时刻产生相同输出。

实现入口是 `RunnerStateInferenceService`。它接收 A 阶段已经查询的规范化日志、计划和基础快照，复用 A 阶段的去重、有效训练、窗口聚合、完成率和主类型分类，不建立第二套数据查询或 Garmin 去重逻辑。

## 派生指标与窗口

- `recent_7d`：结束日及此前 6 个自然日。
- `previous_21d`：`recent_7d` 之前的 21 个自然日，即 `[结束日-27天, 结束日-7天]`。
- `full_28d`：上述两个互不重叠窗口的并集。
- 此前 21 天指标：距离、非休息日志次数、有效训练次数、平均有效 RPE、RPE 覆盖率、计划数、已完成计划数和完成率。数据充分性使用有效训练次数，不把只有空壳日志的记录算作有效基线。
- 周级指标：从 28 天起点开始划分四个互不重叠的 7 个自然日桶；`active` 表示该桶至少有一次有效非休息训练。周训练次数 CV 使用四个桶的总体标准差除以均值；均值为 0 时返回 `null`。
- 高强度指标：仅复用 `HIGH_INTENSITY_TYPES`。同一天多次高强度算多次 session，但连续日只按不同自然日计算。

`KEY_WORKOUT_TYPES` 与 `HIGH_INTENSITY_TYPES` 不等价。普通长距离属于关键课，但默认不属于高强度。复合训练不能可靠拆段时按主类型处理，并返回 limitation。

## 规则配置

唯一公开默认配置位于 `config/training/runner_state_rules_v1.yaml`，版本为 `runner-state-rules-1.0.0`。配置通过严格 Pydantic Schema 校验；缺文件、YAML 错误、未知字段、越界值或阈值顺序错误都会明确抛出配置错误。

全部默认值：

| 分组 | 参数 | 值 |
| --- | --- | ---: |
| data_sufficiency | minimum_valid_workouts_28d | 6 |
| data_sufficiency | minimum_active_weeks_28d | 2 |
| data_sufficiency | minimum_previous_21d_workouts | 3 |
| data_sufficiency | minimum_previous_21d_active_weeks | 2 |
| data_sufficiency | minimum_rpe_coverage | 0.50 |
| data_sufficiency | minimum_planned_sessions_for_consistency | 4 |
| data_sufficiency | minimum_available_fatigue_signals | 3 |
| volume_trend | decreasing_below | 0.70 |
| volume_trend | stable_upper | 1.25 |
| volume_trend | increasing_upper | 1.50 |
| consistency | high_completion_rate | 0.85 |
| consistency | moderate_completion_rate | 0.60 |
| consistency | high_active_weeks | 4 |
| consistency | moderate_active_weeks | 3 |
| consistency | high_weekly_session_cv | 0.25 |
| consistency | moderate_weekly_session_cv | 0.50 |
| consistency | minimum_average_sessions_per_week_for_high | 2.0 |
| fatigue | rpe_delta_moderate | 0.50 |
| fatigue | rpe_delta_high | 1.00 |
| fatigue | completion_rate_drop | 0.25 |
| fatigue | frequent_high_intensity_sessions | 3 |
| fatigue | consecutive_high_intensity_days | 2 |
| fatigue | elevated_score | 2 |
| fatigue | high_score | 4 |

这些值是产品启发式初值，不是医学阈值，也不是基于真实竞赛用户数据调优的私有参数。

## 推断规则

### 跑量趋势

`previous_21d_weekly_average_km = distance_previous_21d_km / 3`，`volume_ratio = distance_7d_km / previous_21d_weekly_average_km`。

- `< 0.70`：`DECREASING`
- `0.70–1.25`（含边界）：`STABLE`
- `> 1.25–1.50`（含上边界）：`INCREASING`
- `> 1.50`：`SPIKING`

距离缺失、基线不大于 0、此前 21 天有效训练少于 3 次、此前 21 天活跃桶少于 2 个，或基础充分性不足时返回 `UNKNOWN`。权威设计没有给出“接近 0”的数值边界；本实现没有擅自增加 epsilon，只对不大于 0 的基线拒绝计算，并在 metadata 记录 `near_zero_volume_baseline_cutoff_not_defined`，等待规则负责人确认。该结论只描述跑量，因此独立写入 `volume_trend`；`load_trend` 保持 `UNKNOWN`。

### 训练一致性

28 天计划数至少为 4 时优先使用 `PLAN_COMPLETION`：完成率至少 0.85 且四周均活跃为 `HIGH`；完成率至少 0.60 且至少三周活跃为 `MODERATE`；否则为 `LOW`。

计划不足时使用 `ACTIVITY_REGULARITY`：四周活跃、周均至少 2 次且 CV 不超过 0.25 为 `HIGH`；至少三周活跃且 CV 不超过 0.50 为 `MODERATE`；至少两周活跃但波动更大为 `LOW`；数据不足为 `UNKNOWN`。计划数为 0 时完成率保持 `null`。

### 疲劳信号

五类可用信号分别是跑量变化、RPE 相对基线上升、计划完成率下降、连续高强度日和近期高强度次数。跑量 `INCREASING` 加 1、`SPIKING` 加 2；有效 RPE 覆盖均至少 0.50 时，差值达到 0.50 加 1、达到 1.00 加 2；两个窗口完成率均有效且下降至少 0.25 加 1；连续高强度日至少 2 天加 2；近期高强度至少 3 次加 1。

至少三类信号可用才映射状态：0–1 为 `NORMAL`，2–3 为 `ELEVATED`，至少 4 为 `HIGH`；否则为 `UNKNOWN`。无恢复日规则在 v1 禁用。`evidence_coverage` 只是可用信号数除以 5，不是预测概率。

### 训练阶段与保留字段

当前 `TrainingCycle` 没有明确的结构化阶段枚举，自由文本 `phase_name` 不足以可靠映射。因此 `training_phase=UNKNOWN`。本版本也不推断竞技能力或短板：`fitness_state=UNKNOWN`、`load_trend=UNKNOWN`、`weaknesses=[]`。

## Evidence、Reason Code 与风险标记

每条 Evidence 包含 `metric`、`value`、`threshold`、`unit`、`window`、`source` 和 `used`。Reason Code 定义在统一枚举中，避免业务代码散落魔法字符串。风险标记只提示人工复核，不自动改变课表，支持：

- `VOLUME_SPIKE`
- `CONSECUTIVE_HIGH_INTENSITY_DAYS`
- `RPE_ABOVE_BASELINE`
- `RECENT_COMPLETION_DROP`
- `FREQUENT_HIGH_INTENSITY_SESSIONS`

严重程度仅为 `INFO`、`WARNING`、`ATTENTION`；建议动作来自受限枚举。缺少 RPE、心率或计划数据只进入 data quality、reason code 或 limitation，不作为训练风险。

## UNKNOWN 与限制策略

数据不足不会阻断基础快照。未执行的规则返回 `UNKNOWN`、对应 Reason Code、跳过信号和 Evidence 覆盖情况。主要限制包括：复合训练按主类型统计；没有结构化训练阶段；恢复日规则未启用；跑量趋势不等同于综合训练负荷趋势。

## 隐私和开放边界

接口仍只读取当前登录用户，不接受任意 `user_id`。响应不包含邮箱、手机号、Garmin Token、API Key、数据库密码或外部活动原始载荷。公开仓库仅保存通用框架、默认启发式参数、虚构测试和文档；真实用户状态、问卷原文、竞赛评测、私有调优阈值和答辩材料留在私有竞赛仓库。

## 完全虚构示例

```json
{
  "volume_trend": {
    "state": "INCREASING",
    "previous_21d_weekly_average_km": 40.0,
    "volume_ratio": 1.3,
    "reason_codes": ["RECENT_VOLUME_ABOVE_BASELINE"],
    "ruleset_version": "runner-state-rules-1.0.0"
  },
  "training_consistency": {
    "state": "HIGH",
    "basis": "PLAN_COMPLETION",
    "evidence_coverage": 1.0
  },
  "fatigue": {
    "state": "ELEVATED",
    "score": 2,
    "available_signal_count": 4,
    "total_signal_count": 5,
    "evidence_coverage": 0.8
  },
  "inferred_state": {
    "fitness_state": "UNKNOWN",
    "load_trend": "UNKNOWN",
    "training_phase": "UNKNOWN",
    "weaknesses": []
  }
}
```
