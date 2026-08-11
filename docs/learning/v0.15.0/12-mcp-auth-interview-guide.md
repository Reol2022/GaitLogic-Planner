# MCP Remote Authentication Interview Guide

## stdio 与 Streamable HTTP 有什么区别？

stdio 是本地 Host 启动子进程，通过 stdin/stdout 传输 MCP；HTTP 是独立服务，支持多个远程连接。远程端点必须额外处理网络暴露、Origin 和身份认证。

## 为什么远程 MCP 不能让 Client 传 user_id？

user_id 是授权边界而不是业务参数。若 Client 可传它，A 用户就可能请求 B 用户训练数据。GaitLogic 只从通过签名、issuer、audience、purpose、expiry 和活动用户检查的 Token 构造身份。

## Authentication 与 Authorization 有何区别？

Authentication 证明 Token 对应哪个 GaitLogic 用户；Authorization 决定该已验证用户只能访问自己的只读训练事实。Tool 参数也不能覆盖这个服务端身份。

## Bearer Token 和 audience 为什么重要？

Bearer Token 是放在 Authorization header 的凭据。audience 将它绑定给 `gaitlogic-mcp`，避免把为其他 API 签发的 Token 当作 MCP 凭据，也避免把 MCP Token 转发给 Provider 或 Garmin。

## Origin 校验解决什么问题？

它降低浏览器/DNS rebinding 场景中陌生网页直接调用本地或远程 MCP 服务的风险。GaitLogic 只允许精确配置的 Origin；拒绝发生在 Token 查询与 Tool 调用之前。

## 这是不是完整 MCP OAuth？

不是。当前是 GaitLogic authenticated MCP HTTP mode。完整 MCP OAuth 还需要 Protected Resource Metadata、Authorization Server discovery、OAuth 2.1 授权流程、PKCE 等。我们如实保留该限制，而不是因为使用 JWT 就虚称合规。

## 如何证明 A 用户不能读取 B 用户？

测试用两个虚构用户签发不同 MCP Token，调用同一个工具后观察 Coach Tool Registry 只接收 Token 对应的 server-injected user_id。包含 `user_id` 的工具参数被 closed-world Schema 直接拒绝。
