# Agent Productionization

上线前先保持 `AGENT_TRACING_ENABLED=false` 与 `AGENT_METRICS_ENABLED=false` 的安全默认值。启用 Trace 时可使用 `noop` 或可选 OTLP；启用 Metrics 时使用受限的内存聚合。二者任何初始化、写入或聚合失败均只写安全日志，不改变 Tool Policy、规则、Validator、Fallback、HITL 或计划事务。

排查顺序：先看 Metrics 的请求成功率、fallback rate、provider retry rate 和 P95；再用对应的安全 Trace 找到组件；最后用固定 Evaluation 判断模型、Prompt 或知识索引修改是否造成质量退化。
