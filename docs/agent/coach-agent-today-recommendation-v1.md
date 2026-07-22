# 今日训练建议 v1

## 权威数据

`TODAY_RECOMMENDATION` 固定预加载五个只读工具：

1. `get_runner_state`
2. `get_today_workout`
3. `get_recent_training`
4. `get_training_data_quality`
5. `evaluate_today_workout`

数据库与既有 Service 提供事实，Runner State 提供状态，Rule Engine 的只读日评估负责约束和决定；Agent 只编排，LLM 只解释，Validator 最终拦截。模型不得自行计算新训练指标、覆盖规则 decision、编造课表或声明已写入系统。

## 结果结构

`today_recommendation` 包含：

- `decision`
- `planned_workout_status`
- `headline`
- `key_evidence`
- `data_quality`

规则评估的既有内部 decision 被确定性映射为：`PROCEED`、`PROCEED_WITH_CAUTION`、`CONSIDER_ADJUSTMENT`、`REST_OR_RECOVERY` 或 `UNKNOWN`。`planned_workout_status` 必须与今日课表工具返回的 `PLANNED`、`REST_DAY`、`NO_PLAN`、`CYCLE_NOT_ACTIVE` 或 `UNKNOWN` 完全一致。

## 确定性 Validator

`TodayRecommendationValidator` 不调用第二个模型。它检查：

- decision 与规则结果一致；
- planned status 与课表结果一致；
- data quality 与工具结果一致；
- UNKNOWN 有 limitation；
- Context 工具失败时不能声称数据完整；
- HIGH 风险保留 warning；
- REST/RECOVERY 不推荐高强度；
- 无计划或休息日不编造距离、时长或训练课；
- 具体数值必须已经存在于 Context；
- Evidence 必须来自规则命中或 Runner State Evidence；
- 不包含医疗诊断、绝对安全承诺或“已经修改计划”的声明。

任一关键检查失败，模型结果不直接返回用户，进入确定性降级。

## Deterministic Fallback

以下情形触发降级：Provider 未启用/未配置、连接或读取超时、429/5xx、非法结构、Validator 拒绝或只读工具失败。Fallback 不调用 LLM，只复述已经获得的规则 decision、今日计划状态、Runner State 摘要、Evidence 和数据质量。

TODAY 降级时：

- 有有效 decision：用有限模板表达该 decision；
- `NO_PLAN` 与 `REST_DAY` 保持不同语义；
- 数据不足：返回 `UNKNOWN`；
- HIGH 风险：保留人工复核 warning；
- 明确说明模型解释暂不可用；
- 绝不创建新训练内容，也不修改计划。

成功降级返回 HTTP 200、`status=DEGRADED`。如果连安全 Context 都未建立，返回 `UNAVAILABLE`，不猜测答案。

## 虚构示例

```json
{
  "status": "DEGRADED",
  "intent": "TODAY_RECOMMENDATION",
  "risk_level": "MODERATE",
  "today_recommendation": {
    "decision": "PROCEED_WITH_CAUTION",
    "planned_workout_status": "PLANNED",
    "headline": "建议谨慎执行原计划。",
    "key_evidence": ["FICTIONAL_PUBLIC_RULE"],
    "data_quality": "PARTIAL"
  },
  "limitations": [
    {
      "code": "MODEL_EXPLANATION_UNAVAILABLE",
      "message": "模型解释服务暂不可用；以下内容只复述系统规则和已有数据。"
    }
  ]
}
```

示例不对应真实用户，也不构成医疗建议或教练处方。
