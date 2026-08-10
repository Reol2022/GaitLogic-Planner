# Timeout, Retry and Fallback

Timeout 限制一次外部调用最长占用多久；Retry 只针对暂时性传输失败再次尝试；Fallback 在最终失败后用已有确定性训练事实继续给出安全结果。三者不是同一个机制。

Chat 使用 `COACH_AGENT_*_TIMEOUT_SECONDS`、`COACH_AGENT_MAX_RETRIES` 和两项 backoff 配置；Embedding 使用对应的 `KNOWLEDGE_EMBEDDING_*` 配置。最大尝试次数始终是 `max_retries + 1`，默认两次。`RetryPolicy` 使用有上限的指数退避，测试通过注入 sleeper 验证等待值，不会真实 sleep。

Timeout、连接错误、429 与 5xx 可以 retry。400、401、403、结构校验失败、工具调用协议错误、Embedding 维度错误和 Validator 拒绝不会 retry，因为重复发送相同请求不会修复确定性错误。

所有允许的尝试耗尽后，Coach Query Service 仍调用已有 `DeterministicCoachFallback`。TODAY 的 decision、warnings、limitations 和 Canonical Facts 仍来自服务端确定性计算；Embedding/RAG 失败不会伪造知识引用，并会保留受控 limitation。
