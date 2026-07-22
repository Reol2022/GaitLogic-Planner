# Coach Agent 只读训练工具 v1 实现说明

## 数据流

服务端未来入口创建 Session 和 `CoachAgentToolDependencies`，随后使用 `build_coach_agent_tool_registry` 创建请求级 Registry。`AgentTrainingContextBuilder` 根据 Intent 预加载最少数据，Gateway 只接收经过 Pydantic 验证和确定性裁剪的 `AgentContext`。

```text
authenticated user
→ AgentRequest.user_id
→ request-scoped Dependencies / Registry
→ existing read services
→ typed tool outputs
→ intent-aware Context
→ provider-neutral Gateway
```

## 实际复用

- 当前状态：`RunnerStateService.get_current`，新增可信 ID 只读封装。
- 历史：`RunnerStateSnapshotService.list_snapshots`，不加载详情 payload。
- 训练：`training_load_service._query_logs` 的既有 Garmin/手动合并事实口径。
- 今日：活动周期与 `planned_workout_service.get_today_workouts`。
- 周期：生命周期服务新增 eager-load blocks 的只读方法。
- 规则：`training_rule_service.list_rules(is_admin=False)` 与 `evaluate_standard_facts`。
- 今日评估：原 Daily Facts 与 Rule Engine，明确 `persist=False, public_only=True`。

## 安全输出

训练备注压缩空白并限制 240 字符。来源仅输出 MANUAL/GARMIN/IMPORT。规则只输出 code、名称、类别、公开摘要、严重度和 Evidence 引用；不输出条件、阈值、结果表达式或路径。

Runner State 保留 UNKNOWN、Evidence 和 limitation，但不返回 identity.runner_id。历史只返回已保存摘要，不重新计算旧状态。

## 配置

- `AGENT_MAX_CONTEXT_CHARS=50000`
- `AGENT_MAX_RECENT_TRAINING_ITEMS=20`
- `AGENT_MAX_HISTORY_ITEMS=7`
- `AGENT_MAX_EVIDENCE_ITEMS=5`
- `AGENT_MAX_RULE_ITEMS=20`

参数仍受工具 Schema 的更严格硬上限约束。

## 非医疗与非自动调整声明

数据完整度不是预测概率；缺少心率不是风险结论。规则评估只返回产品已有确定性结果，不构成医学诊断，也不会执行建议、创建草稿或修改训练计划。
