# Trace、Metrics 与 Evaluation 的边界

Trace 回答“这一请求经过了什么路径、哪个 Span 失败、耗时多少”；Metrics 回答“过去一段时间 Provider 成功率、重试率和 P95 是否变差”；Evaluation 回答“固定虚构案例上的规则、安全与质量是否退化”。

三者不能混用：Trace ID 不能成为 Metrics label，运行时 Metrics 不能取代离线质量评测，离线评测报告也不能被当成真实用户运行数据。v0.14-C 的 `scripts/evaluate_agent.py` 与 v0.14-E 的 `MetricsRecorder` 因此分别维护。
