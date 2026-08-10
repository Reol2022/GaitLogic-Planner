# Agent Workflow Tracing v1

Phase E 增加轻量 `SafeTracer`、`TraceHandle`、`SpanRecord` 和可替换 `TraceSink`。Weekly Review
记录 `weekly_facts`、`rules.evaluate`、`rag.retrieve`、`llm.generate`、`validator`、`fallback`
和 `finalize`；审批写入记录 `proposal.validate`、`plan.apply` 与 `transaction`。

属性使用固定 allowlist，只允许状态、错误码、工具名、引用数量、Validator 结果、fallback、
Provider 类别、Proposal ID 和计划数量。禁止记录完整 Prompt、用户问题、训练正文、知识摘录、
API Key、reasoning 或 Provider 原始响应。sink 故障会被隔离，Tracing 关闭也不改变业务结果。

该抽象保留 trace/span、parent span、attributes、latency 和 status，可后续实现 OpenTelemetry
adapter；v1 不建设新的长期追踪平台，也不把生产 Trace 数据提交到仓库。
