# OpenTelemetry Adapter

## OpenTelemetry 是什么

OpenTelemetry（OTel）是一套开放的遥测标准，用于将 Trace、Metric 和 Log 输出给不同的可观测性后端。本阶段只实现 Trace Adapter；没有部署 Collector、Jaeger、Tempo、Grafana 或任何云端 SaaS。

## 为什么业务代码不直接依赖 OTel

Coach Agent、训练知识检索、LangGraph、Validator 与计划审批只依赖 `SafeTracer` 和 `TraceSink`。它们不 import OTel SDK，也不处理 exporter 初始化。因此替换 exporter、关闭外部导出或 SDK 缺失，都不会改变训练决策和事务语义。

实现位置：

- `server/observability/tracing.py`：内部安全 Trace API。
- `server/observability/sinks.py`：`OpenTelemetryTraceSink`。
- `server/observability/factory.py`：配置组合与降级。

## 映射方式

内部 `SpanRecord` 转换为 OTel span 名称 `component.operation`。显式属性包括：

| 内部字段 | OTel attribute |
| --- | --- |
| `trace_id` | `gaitlogic.trace_id` |
| `span_id` | `gaitlogic.span_id` |
| `parent_span_id` | `gaitlogic.parent_span_id` |
| `component` / `operation` | `gaitlogic.component` / `gaitlogic.operation` |
| `duration_ms` | `gaitlogic.duration_ms` |
| `status` / `error_code` | `gaitlogic.status` / `gaitlogic.error_code` |
| `fallback` | `gaitlogic.fallback` |
| 白名单 metadata | `gaitlogic.metadata.*` |

OTel SDK 可生成自己的 trace/span ID。本项目不强制复用 UUID，而是始终保留内部关联 ID 作为安全属性。正常同步请求中，Adapter 缓冲“子 Span 先结束”的记录，等根 Span 到达后按父节点优先创建 OTel Span，因此 SDK 中也能表达真实父子关系。

## 配置

默认关闭：

```text
AGENT_TRACING_ENABLED=false
AGENT_TRACE_EXPORTER=noop
```

OTLP/HTTP 是可选依赖：

```text
pip install -e ".[observability]"
AGENT_TRACING_ENABLED=true
AGENT_TRACE_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector.internal:4318/v1/traces
```

端点只能是无用户名、密码、query 或 fragment 的 HTTP(S) URL。配置不完整、OTel 未安装或 exporter 初始化失败时，工厂返回 `NOOP_TRACER`；不会阻塞应用启动或用户请求。

## Context propagation

同一同步请求通过 `ContextVar` 自动传播内部 TraceHandle。LangGraph 周复盘将随机 `trace_id` 与根 `span_id` 放在内部 state 的 `trace_context` 中，不放入公共响应。

HITL 审批跨请求恢复时，checkpoint 仅保存这两个随机标识。恢复调用创建 `hitl.resume_approval` 子 Span。若进程仍在，OTel Adapter 可复用缓存的已结束根 SpanContext；若进程已重启，Adapter 保留内部 parent ID attribute，但不会伪造不存在的 OTel SDK parent context。
