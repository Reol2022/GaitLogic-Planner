# Coach Agent Evaluation v1 设计

## 目标

Evaluation v1 用固定日期、完全虚构的训练事实，重复验证 Coach Agent 的只读工具编排、确定性决策一致性、Provider 降级和安全边界。它是产品回归测试，不是运动科学有效性研究，也不使用第二个 LLM 充当裁判。

## 数据流

```text
cases_v1.jsonl
→ strict Pydantic loader
→ fictional fixture registry
→ AgentTrainingContextBuilder
→ GaitLogicCoachAgent
→ Validator / Deterministic Fallback
→ deterministic assertions
→ metrics
→ JSON + Markdown reports
```

## Case Schema

案例声明公开 Intent、虚构 Fixture、预期 Context/Model 工具、禁止工具、允许状态、确定性 decision、计划状态、必须保留的 warning/limitation 和禁止声明。Schema 拒绝未知字段、非公开 Intent、未知工具、未知 Fixture 和重复 `case_id`。

案例不保存用户身份、真实训练数据、Prompt 全文或模型回答。

## Fixture

Fixture 使用 `2026-07-22T09:00:00+08:00`，注册与生产一致的八个只读工具契约。工具输出通过生产 Pydantic 输出 Schema 校验，但数据仅为内存中的虚构数据。Fixture 支持正常、UNKNOWN、数据缺失、过期、工具失败、Provider 失败和安全拒绝。

## Runner

Runner 复用生产 `AgentTrainingContextBuilder`、`GaitLogicCoachAgent`、`AgentResponseValidator`、`TodayRecommendationValidator` 和 `DeterministicCoachFallback`。离线 Gateway 只根据虚构 Context 生成结构化输出，不读 API Key、不访问网络或数据库。

Trace 中的 `CONTEXT_TOOL_COMPLETED` 与 `MODEL_TOOL_COMPLETED` 分别记录，避免把预加载工具误认为模型主动 Tool Calling。

## Assertions

- 请求状态和 Intent；
- Context 与 Model 必需工具；
- 未授权或禁止工具；
- decision 和 planned status；
- warning 与 limitation 保留；
- UNKNOWN、HIGH、REST_OR_RECOVERY、NO_PLAN 规则；
- 计划写入、绝对安全、虚假工具成功等禁止声明。

文本断言是确定性、可审查的有限规则，不推断模型思维过程。

## Metrics

- `case_pass_rate`：通过案例数 / 总案例数；
- `intent_accuracy`：Intent 一致案例数 / 总案例数；
- `required_tool_recall`：实际执行的必需工具数 / 预期必需工具数；
- `forbidden_tool_call_rate`：调用禁止工具的案例数 / 总案例数；
- `tool_argument_validity`：无 `INVALID_ARGUMENTS` 的案例比例；
- `decision_consistency`：今日 decision 与预期确定性结果一致率；
- `planned_status_consistency`：计划状态一致率；
- `warning_retention_rate`：必须 warning 的保留率；
- `limitation_retention_rate`：必须 limitation 的保留率；
- `fallback_success_rate`：实际进入 Fallback 的案例通过率；
- `unsupported_claim_rate`：出现禁止声明的案例比例；
- `rule_violation_rate`：违反明确规则的案例比例。

分母为零时，适用性指标返回 `1.0`，总案例和 Intent 等基础指标返回 `0.0`。

## 报告安全

JSON 只保存案例 ID、分类、状态、预期/实际工具、预期/实际决策、断言、安全错误码和耗时。不会保存 Prompt、Context、工具完整结果、Provider 原始响应、身份、数据库连接、Token、成本或思维链。

## 退出码

- `0`：全部筛选案例通过；
- `1`：至少一个案例失败；
- `2`：案例集、参数或筛选无效。

## 当前限制

v1 不衡量真实 Provider 的语言质量，也不覆盖 RAG、Weekly Review Agent、写工具、长期记忆、Streaming 或多 Agent。
