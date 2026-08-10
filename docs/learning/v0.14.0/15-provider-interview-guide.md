# Provider Reliability Interview Guide

## Timeout、Retry、Fallback 各解决什么？

Timeout 防止外部调用无限占用请求；Retry 处理可能恢复的短暂故障；Fallback 在重试耗尽后维持确定性产品能力。它们分别位于 Adapter、Reliability Policy 和 Coach Service 的不同层。

## 为什么不是所有错误都 retry？

429、网络中断和部分 5xx 有可能短暂恢复。400 是请求格式问题，401/403 是权限或凭据问题，schema/工具协议/维度错误是确定性兼容问题；重试只会增加延迟、费用和限流风险。

## 什么是 bounded exponential backoff？

第 N 次重试按指数增长等待，但被最大等待值截断。GaitLogic 的 `RetryPolicy` 还限制总重试数，并允许注入 sleeper，所以测试不会真的等待。

## Provider Failure 和 Validator Failure 有何不同？

Provider Failure 发生在外部网络、HTTP 或返回协议层；Validator Failure 表示已经得到的结构化结果违反 GaitLogic 安全约束。前者可能触发 Fallback，后者不能通过重新发送同样的请求来绕过规则。

## Chat 和 Embedding 的差异？

Chat 还要处理 JSON 输出和 Tool Calling 协议；Embedding 还要校验向量数量、顺序、维度和有限数值。DeepSeek thinking-mode 工具调用需要 reasoning_content 回放，当前系统仍然 fail closed，这属于 Provider Tool Protocol 兼容边界，而不是重试问题。

## 如何用 Trace 排查？

Provider Span 只导出 `provider_kind`、attempt、max_attempts、failure_category、retried 和 final_status。根据这些字段可区分一次慢调用、重复 429、连接失败或最终协议失败，而不用记录 Prompt、模型回答或凭据。
