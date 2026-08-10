# Weekly Facts

## 1. 模块目标

`planner_core/weekly_review/aggregation.py::build_weekly_facts()` 将计划、日志和 Runner State 样本合成为确定性周事实。`server/services/weekly_facts_service.py::WeeklyFactsService.build_weekly_facts()` 负责限定当前用户和时间窗口并把 ORM 对象转换成领域 Fact。

## 2. 为什么 Plan 与 Log 分开

Plan 表达“打算做什么”，Log 表达“实际发生什么”。如果把实际结果回写覆盖计划，就无法计算未完成、部分完成、额外训练和计划偏差，也无法审计计划在当时是什么。

```text
PlannedSessionFact ----- explicit planned_workout_id -----> WorkoutSessionFact
        |                         |
        |                         +---- unmatched -> extra/unmatched deviation
        +---- no matching log ----------> missed deviation
```

## 3. 匹配与计算

优先复用显式 `planned_workout_id`；没有显式关联时只在日期与类型能够唯一匹配时关联；同日多个候选保持 ambiguous，不做模糊强绑定。完成率使用已完成计划数除以计划跑步次数；计划数为 0 返回空。距离只对存在值求和，所有值缺失时保持空。

`WeeklyPlannedMetrics`、`WeeklyCompletedMetrics`、`WeeklyAdherenceMetrics` 和 `WeeklyDistributionMetrics` 分别承载计划、实际、遵从与强度分布。`WeeklyDeviation` 保存偏差类型、日期、期望、实际和证据码。

## 4. Canonical Weekly Facts

Canonical 表示服务端权威装配：模型可以引用这些事实，但不能重新定义完成率、疲劳状态、warning 或 data quality。`result_hash` 从排除生成时间后的规范化 JSON 计算，因此同输入结果稳定。

## 5. 数据质量

冲突匹配为 `CONFLICTED`；计划和日志都为空为 `INSUFFICIENT`；缺失字段、未匹配日志或 Runner State 样本不足为 `PARTIAL`；否则为 `COMPLETE`。限制写入 classification，而不是把缺失数据用 0 填满。

## 6. 关键边界

- 取消计划不进入完成率分母。
- 活动指纹重复只统计一次。
- 同日多练保留为多条事实。
- 长距离是关键训练但不自动等于高强度。
- 周窗口由 `WeeklyFactsRequest` 校验不超过 7 个自然日。
- 当前实现不根据缺失睡眠或心率推断医学风险。

## 7. 测试方法

`tests/test_weekly_facts_domain.py` 覆盖显式关联、唯一匹配、歧义、重复活动、少跑、多跑、关键课、跨月和确定性哈希。`tests/test_weekly_facts_service_boundaries.py` 验证用户隔离、查询窗口和只读行为。公开评测入口是 `scripts/evaluate_weekly_adaptive.py`。

## 8. 常见错误

最危险的错误是把缺失距离当 0、把无计划当休息日、用日期字符串直接比较时区、或在 LLM Prompt 中重新计算事实。另一个错误是只按同日强行匹配，导致双练关联错位。

## 9. 面试回答

30 秒回答：我把计划态和执行态保留为两组事实，先显式关联再做保守唯一匹配；聚合结果是严格 Pydantic Schema，缺失值不伪造，分类、证据和哈希均由服务端确定，因此 LLM 无法改写训练事实。

追问时说明为什么不用数据库快照：周事实当前按需计算，避免派生状态和源数据不一致；需要历史审计时保存的是计划版本和状态快照，而不是让模型结果成为事实源。
