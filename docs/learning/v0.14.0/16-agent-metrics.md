# Agent Metrics

实现位于 `server/observability/metrics.py`。`MetricsTraceSink` 被动接收已经完成且经过 Trace 白名单过滤的 `SpanRecord`，再由 `MetricsRecorder` 生成计数和延迟指标。

当前真实采集范围包括 Coach 请求、工具调用、知识检索、Provider、Validator、Fallback、Weekly Review 与 Proposal 批准/拒绝。没有对应 Span 的指标不会伪造，例如不存在独立的模型 token 成本指标。

`InMemoryMetricsSink` 只保存聚合计数与每个低基数序列的有界延迟样本，默认最多 2048 条。因此可计算 P50/P95，但不是长期生产监控库；生产接入 Collector 前应使用外部 histogram/summary 后端。
