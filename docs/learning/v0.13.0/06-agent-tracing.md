# Agent Tracing

## 1. 目标

普通日志描述离散事件，Trace 描述一次请求内父子 Span 的因果与耗时。v0.13 需要区分事实查询慢、RAG 失败、Provider 超时、Validator 拒绝还是计划事务失败。

## 2. 实现

`server/observability/tracing.py` 定义 `TraceSink`、`InMemoryTraceSink`、`TraceHandle`、`SpanRecord` 和 `SafeTracer`。`start_trace()` 创建根标识，`span()` context manager 记录开始、结束、latency、status 和安全错误码。Sink 失败被隔离，不影响业务。

```text
weekly_review.request
  +-- weekly_facts
  +-- rules.evaluate
  +-- rag.retrieve
  +-- llm.generate
  +-- validator
  +-- fallback (optional)
  +-- finalize

adaptive_plan.request
  +-- proposal.validate
  +-- plan.apply
  +-- transaction
```

## 3. 安全属性

Tracer 只接受 allowlist 元数据。禁止完整 Prompt、Query、训练正文、Provider 原始响应、API Key、数据库 URL 和 reasoning_content。公共 API 不返回 trace_context。

## 4. 故障定位

- Tool 未调用：检查相应 Span 是否缺失以及上游状态。
- RAG 失败：`rag.retrieve` 为 error，但图应继续并增加 limitation。
- Provider 超时：`llm.generate` 失败，随后应出现 fallback。
- Validator Reject：validator 状态失败并进入 fallback，而不是返回模型正文。
- Proposal Apply 失败：`plan.apply` 或 transaction 失败，数据库应 rollback。

## 5. OpenTelemetry 扩展

当前抽象保留 Sink 接口，未来可实现 OTel adapter，把 trace_id、parent/child、attributes、status 映射到 SDK。业务层不需要直接依赖 exporter，也不会因遥测后端不可用而阻断请求。

## 6. 测试

`tests/test_agent_workflow_tracing.py` 验证唯一 trace、父子关系、延迟、error、fallback、安全过滤、disabled 无影响和 sink failure 隔离。图与批准服务测试也验证业务结果不依赖 tracing。

## 7. 常见错误

不要把 Trace 当调试数据垃圾桶；敏感正文进入遥测平台同样是泄漏。不要让 exporter 异常冒泡；不要使用用户可控 trace_id 作为授权依据；不要只记录成功路径而丢失 fallback。

## 8. 面试回答

30 秒回答：我先做轻量 SafeTracer，把节点耗时、状态和错误码结构化，并用 Sink 隔离后端。它不记录 Prompt 或训练正文，关闭或写入失败都不改变业务。接口与父子模型对齐 OpenTelemetry，后续可接 OTLP 而无需重写业务节点。
