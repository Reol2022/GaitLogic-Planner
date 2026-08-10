# Trace 与 Span

## 定义

Trace 表示一次逻辑请求的完整执行树；Span 表示其中一段有边界的操作，例如一次工具调用、一次向量检索或一次 Validator 校验。`TraceHandle` 只携带随机生成的 `trace_id` 与根 `span_id`，不携带用户身份或请求正文。

`SpanRecord` 的统一字段为：

| 字段 | 含义 |
| --- | --- |
| `trace_id` | 同一逻辑请求的关联标识 |
| `span_id` | 当前操作标识 |
| `parent_span_id` | 父操作标识；根 Span 为 `null` |
| `component` | 组件边界，例如 `tool`、`knowledge`、`validator` |
| `operation` | 组件内操作，例如 `invoke`、`retrieve` |
| `start_time` | UTC 带时区开始时间 |
| `duration_ms` | 单调时钟测得的耗时 |
| `status` | `SUCCEEDED`、`FAILED` 或受控拒绝状态 |
| `error_code` | 安全错误码，不包含异常原文 |
| `fallback` | 是否走了确定性降级 |
| `metadata` | 白名单中的少量运行元数据 |

为了兼容 v0.13 轻量实现，`name`、`started_at`、`ended_at`、`latency_ms`、`attributes` 仍保留为只读兼容访问方式。

## 父子关系

`SafeTracer` 用请求局部的 `ContextVar` 维护当前 Trace 与 Span。进入根请求 Span 后，注册表中的 Tool Span 自动继承父节点；知识工具在 Tool Span 内部创建 `knowledge.retrieve`，因此能直接看到“某个工具慢”还是“工具内部检索慢”。

跨 LangGraph 节点时，工作流状态只保存随机 Trace 标识和根 Span 标识，不保存事实正文。第一个节点创建根 Span，后续节点复用同一根。

## 状态与错误

业务异常会原样抛出，Span 仅标为 `FAILED` 并使用通用安全码 `TRACE_OPERATION_FAILED`。业务已知失败则可设置既有错误码。追踪绝不序列化异常字符串，因为其中可能含 Provider、数据库或用户内容。
