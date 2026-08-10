# Provider Reliability

GaitLogic 通过 `server/provider_reliability.py` 为 Chat 与 Embedding Adapter 提供同一套可靠性边界。它只处理一次外部 Provider 调用的超时、连接问题、HTTP 状态和安全失败分类；不会改变 Agent Tool Policy、Validator、Fallback、训练规则或计划写入。

Chat 入口是 `server/agent/providers/openai_compatible.py`，Embedding 入口是 `server/knowledge_retrieval/embeddings/openai_compatible.py`。两者都保留各自的协议校验职责，但共用 `ProviderFailureCategory`、`RetryPolicy`、`classify_provider_exception` 和 `ProviderCallReliability`。

每次调用都只产生安全摘要：尝试次数、最大次数、是否重试、最终状态和失败类别。请求体、Prompt、训练上下文、响应正文、Key、向量与 reasoning_content 不会写入该摘要。
