# TraceSink 与安全导出

## Sink 分层

```text
业务 Agent / Workflow
        ↓
SafeTracer + SpanRecord
        ↓
TraceSink
 ├── NoopTraceSink
 ├── InMemoryTraceSink（测试）
 └── OpenTelemetryTraceSink（可选 OTLP）
```

`TraceSink.write(span)` 只接收已完成、已脱敏的 `SpanRecord`。Sink 没有业务数据库 Session、没有用户身份，也不访问 Agent Context。

## 三种 Sink

- `NoopTraceSink`：显式丢弃，用于启用内部插桩但不输出的安全环境。
- `InMemoryTraceSink`：测试使用，保存 Span 列表，不连接网络。
- `OpenTelemetryTraceSink`：将白名单字段适配为 OTel spans。只有安装 optional observability 依赖并完成端点配置时才初始化。

## 失败隔离

`SafeTracer` 已捕获 `sink.write` 失败；OTel Sink 自身还捕获 SDK 和 exporter 错误，记录固定安全日志码 `OTEL_EXPORT_FAILED`。不会记录 endpoint、异常文本、Prompt、Provider 原文或凭据。

这意味着 exporter 断网、Collector 不可用、SDK 缺失都不会：

- 改变 Intent 或 Tool Policy；
- 改变 Validator/Fallback；
- 回滚训练计划事务；
- 触发 Provider 重试；
- 让用户请求返回失败。

## metadata 白名单

OTel Adapter 再次执行显式白名单检查，即使调用方手工构造 `SpanRecord` 也不会将任意 dict 转换为 attributes。允许的是 Intent、Tool 名称、图节点、校验结果、Fallback 原因、Provider 状态、知识检索状态和少量数量/时延字段。

禁止导出：用户问题、Prompt、Context、训练正文、用户 ID/email、Token、API Key、数据库 URL、Provider 原始响应、reasoning_content、Embedding vector 与知识 chunk 正文。

## 后续部署位置

未来可在应用进程外部署 OTel Collector，应用只向内网 OTLP endpoint 输出；Collector 再转发到 Tempo、Jaeger、Grafana Cloud 或其他后端。接入这些后端只需部署和配置变化，Agent Core、Tool、Validator 和训练规则无需重写。
