# Runner State Model v1

## 模型目标

Runner State Model v1 是 GaitLogic 的公开产品能力。v0.10.3-A 只建立可追溯的状态数据契约、7 天/28 天基础聚合和数据完整度评估。快照按请求计算，不写入数据库，不调用大语言模型，也不生成或调整训练计划。

## 输入数据

- `UserAccount.id`：仅用作内部跑者引用；不读取或返回用户名、邮箱、密码等字段。
- 活动的 `TrainingCycle`：提供结构化比赛日期和目标成绩文本。
- 有效 `PlannedWorkout`：提供计划次数与主训练类型。
- `WorkoutLog`：提供规范化状态、公里距离、秒级时长、RPE 和心率。
- Garmin/外部活动不会直接汇总。它们必须先经过既有的活动规范化、重复识别、复合活动合并和 `WorkoutLog` 关联流程。

## 状态结构

快照分为：`identity`、`goal_context`、`recent_training`、`intensity`、`inferred_state` 和 `data_quality`。Schema 位于 `server/schemas/runner_state.py`。

`identity` 只包含 `runner_id`、生成时间、时区和窗口边界。`goal_context` 仅返回数据库中可可靠解释的结构化字段。当前 `TrainingCycle` 没有结构化比赛距离字段，因此 `race_distance` 返回 `null`，不会从比赛名称猜测距离。

## 指标定义

- 距离：已完成训练中非负 `actual_distance_km` 的和，保留 2 位小数；全缺失时返回 `null`，真实零距离保留为 `0`。
- 时长：已完成训练中非负 `actual_duration_seconds / 60` 的和，保留 1 位小数；全缺失时返回 `null`。
- `sessions`：窗口内已有日志的非休息训练次数。
- `completed_sessions`：状态属于现有 `COMPLETED_STATUSES` 的训练次数。
- `planned_sessions`：窗口内生命周期为 `planned` 且主类型不是休息的计划次数。
- 完成率：`completed_planned_sessions / planned_sessions`，保留 4 位小数。计划数为 0 时返回 `null`。
- 平均 RPE：只对已完成训练且 RPE 位于现有合法范围 0–10 的值求平均。缺失值不替换为 0，非法值排除并写入 limitation。
- RPE/心率覆盖率：有合法字段的已完成训练数除以已完成训练总数。心率存在表示平均或最大心率至少一个可用。
- 有效训练：已完成且至少有一个非负距离或时长字段的规范化训练日志。
- 关键课：复用现有 `KEY_WORKOUT_TYPES`，即间歇、节奏和长跑。
- 最近关键课天数：当前窗口结束日期减去最近一条规范化关键课日志日期。

## 7 天与 28 天窗口

两个窗口都包含结束日：7 天窗口为 `[结束日 - 6 天, 结束日]`，28 天窗口为 `[结束日 - 27 天, 结束日]`。生产默认时区复用项目现有 `Asia/Shanghai`，实现使用 `zoneinfo.ZoneInfo` 和日期运算，不依赖固定日期字符串或固定 UTC 偏移。

## 强度分类现状与限制

分类复用现有训练类型集合：

- easy：`easy`、`recovery`
- hard：`interval_speed`、`tempo`
- moderate：`easy_with_speed`、`long_run`、`mixed`

v1 按训练主类型归类整次训练距离。对于混合训练和轻松跑加速度段，本阶段不猜测各段距离；`limitations` 会包含 `composite_workout_intensity_segments_not_split`。未知类型距离仍计入总距离，但不会进入 easy/moderate/hard 桶。Garmin 已可靠解析的活动仍通过既有流程汇入规范化日志，状态服务不创建第二套活动去重或合并规则。

## 数据质量计算

`confidence` 是数据完整度分数，不是机器学习置信度，也不表示运动科学结论。存在已完成训练时，计算以下六项覆盖率的算术平均并保留 4 位小数：

1. 有效训练数 / 已完成训练数
2. 距离覆盖率
3. 时长覆盖率
4. RPE 覆盖率
5. 心率覆盖率
6. 计划数据可用性（有计划为 1，否则为 0）

没有已完成训练时分数为 0。数据质量等级仅描述完整度：无已完成训练为 `NONE`；分数小于 0.5 为 `LOW`；0.5 至小于 0.8 为 `MEDIUM`；至少 0.8 为 `HIGH`。

`available_fields` 和 `missing_fields` 明确列出字段可用性；负距离、负时长、非法 RPE、缺少计划、复合训练无法拆分等情况记录在 `limitations`。

## UNKNOWN 策略

以下字段在 v0.10.3-A 始终为 `UNKNOWN`：`fitness_state`、`fatigue_state`、`load_trend`、`training_consistency` 和 `training_phase`。`weaknesses`、`risk_flags` 始终为空列表。本阶段不定义疲劳阈值、伤病风险规则或跑者等级。

## 隐私、安全与开源边界

接口只依赖当前登录用户，不接受 `user_id`。响应不包含姓名、邮箱、手机号、Garmin 令牌、API Key 或原始外部活动载荷。公开仓库可包含 Schema、确定性聚合、数据质量代码、测试和虚构示例；真实用户快照、问卷原始数据、竞赛评测结果、私有阈值和提示词不得进入公开仓库。

## 示例响应

以下跑者和数据完全虚构：

```json
{
  "snapshot": {
    "identity": {
      "runner_id": 900001,
      "generated_at": "2026-07-15T12:00:00+08:00",
      "timezone": "Asia/Shanghai",
      "calculation_window_end": "2026-07-15",
      "calculation_window_start_7d": "2026-07-09",
      "calculation_window_start_28d": "2026-06-18"
    },
    "goal_context": {
      "race_distance": null,
      "race_date": "2026-10-25",
      "target_time_seconds": 12600,
      "weeks_remaining": 14.6
    },
    "recent_training": {
      "distance_7d_km": 42.5,
      "distance_28d_km": 158.2,
      "duration_7d_minutes": 238.5,
      "duration_28d_minutes": 905.0,
      "sessions_7d": 5,
      "sessions_28d": 19,
      "completed_sessions_7d": 5,
      "completed_sessions_28d": 18,
      "planned_sessions_7d": 6,
      "planned_sessions_28d": 20,
      "completion_rate_7d": 0.8333,
      "completion_rate_28d": 0.9,
      "average_rpe_7d": 5.8,
      "average_rpe_28d": 5.6
    },
    "intensity": {
      "easy_distance_7d_km": 24.5,
      "moderate_distance_7d_km": 12.0,
      "hard_distance_7d_km": 6.0,
      "easy_distance_28d_km": 91.2,
      "moderate_distance_28d_km": 43.0,
      "hard_distance_28d_km": 24.0,
      "hard_distance_ratio_7d": 0.1412,
      "hard_distance_ratio_28d": 0.1517,
      "quality_sessions_7d": 2,
      "quality_sessions_28d": 7,
      "long_run_distance_7d_km": 12.0,
      "long_run_distance_28d_km": 43.0,
      "days_since_last_quality_session": 2
    },
    "inferred_state": {
      "fitness_state": "UNKNOWN",
      "fatigue_state": "UNKNOWN",
      "load_trend": "UNKNOWN",
      "training_consistency": "UNKNOWN",
      "training_phase": "UNKNOWN",
      "weaknesses": [],
      "risk_flags": []
    },
    "data_quality": {
      "data_quality_level": "MEDIUM",
      "confidence": 0.7361,
      "available_fields": ["training_logs", "actual_distance_km", "actual_duration_seconds", "rpe", "heart_rate", "planned_workouts", "goal_context", "intensity_classification"],
      "missing_fields": [],
      "valid_workout_count_7d": 5,
      "valid_workout_count_28d": 18,
      "rpe_coverage_7d": 0.8,
      "rpe_coverage_28d": 0.7778,
      "heart_rate_coverage_7d": 0.6,
      "heart_rate_coverage_28d": 0.5,
      "limitations": ["intensity_distance_uses_main_workout_type"]
    }
  }
}
```

## 后续计划

下一阶段仅进入 v0.10.3-B 跑者状态推断规则设计：为当前 `UNKNOWN` 字段定义可审查、可测试、非医疗诊断的确定性规则。智能体、计划生成和动态调整不属于本模型阶段。
