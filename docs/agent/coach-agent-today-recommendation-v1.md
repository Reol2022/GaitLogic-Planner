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

这是公共 Coach API 的稳定结构。Provider 内部 TODAY 输出只有
`answer`、`summary` 和 `key_evidence_ids`。模型不输出 decision、planned status、
risk、data quality、headline、warnings 或 limitations；这些训练事实全部由服务端
从已验证的 Context、只读工具和规则结果确定。

Provider 从本次请求的 `available_evidence` Catalog 中选择
`key_evidence_ids`。这些 ID 采用 `evidence_1...n`，只在单次请求中有效，不包含
用户 ID、数据库 ID、路径或 Evidence 原文，也不会进入 OpenAPI 或前端响应。

内部数据流为：

```text
Canonical Evidence
→ 请求级 Evidence Catalog
→ Provider 选择严格 ID
→ 服务端校验 ID
→ 按 Canonical 原始顺序还原文本
→ 服务端装配 decision / plan / risk / quality / notices / headline
→ Deterministic Validator
→ 公共 key_evidence
```

模型不能改写、概括或创造 Evidence。未知 ID、大小写变化、前后空白、重复 ID、
数字索引、Evidence 原文冒充 ID，以及在存在 Canonical Evidence 时返回空选择，
都会触发安全降级。系统不使用模糊匹配、编辑距离、Embedding、第二个 LLM 或
自动文本替换。

`build_authoritative_today_facts()` 是成功路径与 Fallback 共用的权威装配入口：

- decision 来自既有日评估的确定性映射；
- planned status 来自今日计划工具；
- risk、warnings 和 limitations 来自规则评估及已验证工具结果；
- data quality 来自数据质量工具；
- headline 使用有限服务端模板；
- Canonical Evidence 由服务端 materialize。

Provider 的 answer 和 summary 只能解释这些事实，不能成为训练结论来源。

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
- Materialized Evidence 必须逐字来自规则命中或 Runner State Evidence；
- 不包含医疗诊断、绝对安全承诺或“已经修改计划”的声明。

任一关键检查失败，模型结果不直接返回用户，进入确定性降级。

Fallback 不依赖 Provider Evidence ID，继续直接从确定性 Context 取得 Canonical
Evidence，因此 Provider 引用失败不会污染降级结果。

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
