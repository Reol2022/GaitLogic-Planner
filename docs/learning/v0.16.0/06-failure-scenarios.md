# Qdrant 故障处理

常见故障与安全动作如下：

| 场景 | 系统动作 | 不会发生的事 |
| --- | --- | --- |
| `qdrant-client` 未安装 | 初始化/Readiness 失败并给出安全配置状态 | 不会静默伪装为 Qdrant 已启用 |
| URL 无效或带凭据 | Settings 拒绝配置 | 不会把 URL 原文写到日志 |
| collection 缺失或 stale | Manifest/Store 校验失败 | 不会返回伪造知识引用 |
| 查询失败 | 既有 Knowledge Tool 安全降级 | 不会改变 TODAY 确定性建议 |
| payload 损坏 | Adapter 拒绝内部记录 | 不会将 payload 原文暴露给客户端 |
| Trace/Metric Sink 失败 | 业务检索继续 | 不会让监控故障变成 Coach 故障 |

排查时先检查 `KNOWLEDGE_VECTOR_STORE` 与 Index Manifest 的 `vector_store` 是否一致，再验证 Corpus root hash、Embedding provider/model/dimensions 和 collection count。不要用重建索引来掩盖不一致；先确认部署配置与目标版本。
