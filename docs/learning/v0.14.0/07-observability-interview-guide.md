# 可观测性面试说明：OTel Adapter 与 Trace Sink

## 为什么引入 TraceSink abstraction？

代码在 `server/observability/tracing.py`、`server/observability/sinks.py`。TraceSink 将业务插桩与导出技术分开：Agent 只结束一个安全 Span，OTel、测试内存 Sink 或未来其他 exporter 都在边界之外实现。

替代方案是业务代码直接调用 OTel SDK。它实现快，但会把 SDK 初始化、上下文和 exporter 故障耦合到 Agent、RAG 与事务代码，难以测试和替换。

## Trace 和 Span 如何映射到 OTel？

内部 `SpanRecord` 有随机内部 ID、组件、操作、时间、状态、错误码与白名单 metadata。Adapter 使用 `component.operation` 作为 OTel 名称，把内部 ID 作为 `gaitlogic.*` attribute。SDK 可以使用自己的 ID；两套 ID 的映射在属性中可审计。

测试在 `tests/test_opentelemetry_trace_sink.py` 使用 Fake OTel tracer，验证不联网时根/子/嵌套关系、失败状态、Fallback 属性和安全字段过滤。

## Context propagation 是什么？

它是将同一次请求的 trace/span 关系传递到下游操作。同步 Coach 请求使用 Python `ContextVar`；LangGraph 将只含随机 Trace 标识的 context 放入内部 state；HITL checkpoint 恢复只传播这些 ID，不传播用户内容。

跨进程恢复时不存在原生 OTel SDK context，不能声称存在。当前实现会保留内部 parent ID；只有同一进程内缓存仍在时才恢复实际 SDK 父关系。

## 为什么 exporter 失败不能影响业务？

观测不是训练决策的输入。`SafeTracer` 和 OTel Sink 分别隔离错误，使用固定日志码而非异常正文。测试验证 exporter `start_span` 失败后业务 `with` 块仍可正常完成。

## 为什么 metadata 必须白名单？

Telemetry 常被发送到外部系统，自动把任意 dict 放入 attribute 极易把 Prompt、训练记录、数据库 URL 或 Key 送出。GaitLogic 在 Trace API 与 OTel Adapter 两层都过滤 metadata。

## 如何以后接 Grafana、Jaeger 或 Tempo？

安装 optional observability 依赖，部署受控 OTel Collector，在配置中填写不含凭据的内网 OTLP endpoint。Collector 负责导出到具体后端。这样替换 Jaeger/Tempo/Grafana 不需要修改 Agent 核心逻辑。
