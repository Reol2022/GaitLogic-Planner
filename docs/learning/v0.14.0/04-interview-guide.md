# v0.14.0-A 面试说明：Agent 可观测性

## 1. 为什么 Agent 需要 Trace？

Agent 请求跨越策略校验、事实工具、RAG、Provider 和 Validator。单条日志很难判断一次请求是慢在模型、检索还是工具。Trace 将这些有因果关系的操作放到同一请求树中，便于定位延迟和降级原因。

代码：`server/observability/tracing.py`、`server/agent/orchestrator.py`、`server/agent/registry.py`。

测试：`tests/test_agent_observability.py`、`tests/test_agent_training_knowledge_tool.py`。

## 2. Trace 和普通日志有什么区别？

日志是离散事件，适合记录单点信息；Trace 用 `trace_id`、`span_id` 和 `parent_span_id` 表示调用关系及耗时。这里仍保留普通安全日志，但不会以日志替代请求树。

替代方案是仅依赖应用日志；缺点是无法可靠关联并发请求中的 Provider、Tool 与 RAG 操作。

## 3. Span 是什么？

Span 是一个明确起止边界的操作记录。本项目的 Span 包括组件、操作、开始时间、耗时、状态、错误码、是否降级和安全元数据。比如 `tool.invoke` 是工具边界，`knowledge.retrieve` 是它内部的检索边界。

## 4. 为什么要有 parent/child span？

父子关系允许定位总耗时的归属：一个 Tool 调用慢，可能慢在它内部的知识检索，也可能慢在工具自己的数据读取。请求局部 `ContextVar` 保证并发请求不会混用父节点。

## 5. 为什么不能直接记录 Prompt 和模型原文？

Prompt、Context 和模型原文可能包含训练记录、身份信息、Provider 内容或推理文本。它们既不是定位耗时所必需，也会扩大隐私和凭据泄漏面。因此采用 metadata 白名单：未知字段、`user_id`、`prompt` 等均被丢弃。

曾出现的问题：Provider 和数据库异常常带有内部细节。Span 只保存安全错误码，异常仍按业务层原语义处理。

## 6. Trace 系统故障为什么不能影响业务？

Trace 是旁路观测，不是决策依赖。`TraceSink.write` 被独立 try/except 包裹；Sink 故障不会改变 API 响应、Validator、Fallback 或计划事务。测试 `test_sink_failure_does_not_change_request_completion` 验证了这一点。

## 7. OpenTelemetry 放在哪里？

`server/observability/sinks.py` 的 `OpenTelemetryTraceSink` 已将已过滤的 `SpanRecord` 映射为 OTel Span；`server/observability/factory.py` 在应用组合根按配置注入。OTel SDK 不渗入 `AgentToolRegistry`、训练规则或 SQLAlchemy 服务，因此可以更换 exporter 而不改业务代码。

## 8. 如何通过 Trace 定位 Tool 慢、RAG 慢、LLM 慢？

按同一 `trace_id` 比较各 Span 的 `duration_ms`：查看 `tool.invoke` 判断工具总体耗时，再查看其 `knowledge.retrieve` 子节点判断是否由检索造成；查看 `provider.generate` 判断 LLM 网关时间；查看 `graph_node` 定位 LangGraph 节点。只依据安全状态、错误码和白名单元数据排查，绝不为排障打开 Prompt 或模型原文记录。
