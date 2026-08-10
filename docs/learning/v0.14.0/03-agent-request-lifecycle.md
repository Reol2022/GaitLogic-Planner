# Agent 请求生命周期

## Coach 查询

1. `CoachAgentQueryService.query` 创建 `coach_api.query` 根 Span，仅记录已解析 Intent。
2. `GaitLogicCoachAgent.run` 在根下创建 `agent.orchestrate`。
3. Validator 校验请求；失败时保留原有拒绝语义。
4. `AgentTrainingContextBuilder` 通过只读 Registry 预加载训练事实。每次 Registry 调用形成 `tool.invoke`。
5. 已启用的知识工具在 Tool Span 内创建 `knowledge.retrieve`。只记录检索状态与结果数量，不记录 query、摘录、向量或内部路径。
6. Provider 调用形成 `provider.generate`；Provider 原始响应仍不进入 Trace。
7. Validator 校验结构化输出。
8. 若模型不可用、工具失败或输出不安全，查询服务执行原有 `DeterministicCoachFallback`，形成 `fallback.deterministic_coach_response`。确定性建议仍由现有事实和规则产生。

## 周复盘与计划审批

周复盘 LangGraph 的每个节点均是同一 Trace 下的 Span，`graph_node` 用于定位慢节点。审批服务保留原有锁、版本号和提交顺序，只额外旁路记录 proposal 校验、计划应用、版本记录与事务提交的耗时。

## 读取 Trace 的方法

当前版本不对前端或公共 API 暴露 Span。测试或未来受控运维组合根可使用 `InMemoryTraceSink` 或安全 exporter 查看：

- `tool.invoke` 较慢而子节点不存在：关注工具自身的训练服务或数据库查询。
- `knowledge.retrieve` 较慢：关注 Embedding、索引打开或检索，不读取用户 query。
- `provider.generate` 较慢：关注 Provider 状态和受控 timeout。
- `validator` 失败：查看安全错误码与 `validator_result`，不要查看模型原文。
- `fallback=true`：说明正常业务已使用确定性降级，而不是追踪系统造成失败。

Trace 不是用户行为分析、长期对话记忆或训练日志存档。本阶段不持久化 Trace，也没有新增数据库迁移。
