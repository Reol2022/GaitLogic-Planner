# v0.14.0-A：Agent 可观测性

## 目标

本阶段为 GaitLogic 的 Agent 与既有自适应训练流程补充统一、可选、旁路的 Trace/Span 模型。它用于回答“某次请求经过了哪些受控组件、每段耗时多少、何处失败或触发降级”，而不是记录用户训练内容或模型对话。

实现位于 `server/observability/tracing.py`。该模块不依赖任何具体 SaaS，也不写数据库；调用方可注入 `TraceSink`，默认使用 `NOOP_TRACER`，因此关闭追踪时业务行为保持原样。

## 已覆盖的链路

- Coach Query 根请求：`coach_api.query`
- Agent 编排：`agent.orchestrate`
- 请求与模型输出校验：`validator.validate_request`、`validator.validate_output`
- Provider 调用：`provider.generate`
- Agent 工具调用：`tool.invoke`
- 训练知识检索：`knowledge.retrieve`
- LangGraph 周复盘节点：`weekly_facts`、`rules.evaluate`、`rag.retrieve`、`llm.generate`、`validator`、`fallback`、`finalize`
- 确定性 Coach 降级：`fallback.deterministic_coach_response`
- 计划审批的验证、写入、版本化与事务：`proposal.validate`、`plan.apply`、`versioning.create_plan_version`、`transaction`

这些 Span 只描述系统操作，不改变 Intent Policy、Tool Policy、Validator、Fallback 或训练计划事务。

## 开关与注入

`SafeTracer(sink, enabled=True)` 只在同时满足“启用”和“存在 sink”时导出 Span。业务组合根可以注入它，例如测试中的 `InMemoryTraceSink`；没有注入时仍使用 `NOOP_TRACER`。

Trace Sink 的 `write(span)` 发生异常时会被安全吞掉。导出失败不会回滚数据库事务、不会重试 Provider、不会影响 API 响应。

## 安全元数据

Trace 使用白名单。允许的字段包括：`intent`、`tool_name`、`graph_node`、`validator_result`、`fallback_reason`、`provider_status`、`knowledge_retrieval_status`、`operation_type`、`latency` 以及有限的既有运行指标。

下列内容不会被导出：用户问题、Prompt、Context、训练日志正文、Provider 原文、`reasoning_content`、密钥、Token、向量和用户身份字段。未知键、嵌套对象与列表也会丢弃。

## OpenTelemetry 适配

v0.14.0-B 已由 `server/observability/sinks.py` 实现 `OpenTelemetryTraceSink`，并由 `server/observability/factory.py` 依据安全配置组合。Adapter 消费 `TraceSink.write(SpanRecord)`，将安全字段映射为 OTel attributes；OTel SDK、网络 exporter 或采样失败仍不会进入 Agent、训练规则或事务代码。
