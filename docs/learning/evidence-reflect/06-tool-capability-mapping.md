# Tool Capability Mapping

`AgentToolDefinition.provided_fact_domains` 是 Reflect 使用的最小能力元数据。它不改变 Tool Schema 的输入，也不绕过 Registry：

- `get_recent_training`：跑量、频率、近期强度、负荷、计划执行、存在时的 RPE。
- `get_runner_state`：负荷、近期强度、恢复、存在时的主观疲劳。
- `get_runner_state_history`：负荷与恢复趋势。
- `get_today_workout`：今日计划。
- `get_current_training_cycle`：训练阶段和计划上下文。
- `retrieve_training_knowledge`：仅 `training_knowledge`。

Reflect 仍必须通过 allowed intents、只读属性、Pydantic 参数校验和服务端 user identity 注入。
