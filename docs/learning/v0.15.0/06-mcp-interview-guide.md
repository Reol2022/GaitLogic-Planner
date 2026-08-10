# MCP 面试要点

## 为什么已有 Tool Calling 还要 MCP？

内部 Tool Calling 解决 Agent 在 GaitLogic 内怎样使用训练事实；MCP 解决可信外部 Host 怎样发现并调用受控能力。二者边界不同，MCP 不应复制规则或 SQL。

## Host、Client、Server 分别是什么？

Host 是承载用户体验的应用；Client 建立协议会话并发送 `tools/list`、`tools/call`；Server 声明并执行工具。本阶段 GaitLogic 只实现 Server，测试中的 SDK Client 是协议对端。

## Tool、Resource、Prompt 有什么差别？

Tool 是可调用函数；Resource 是可读取的命名内容；Prompt 是服务器提供的提示模板。本阶段仅 Tool，避免在认证和远程边界尚未完成前扩大暴露面。

## stdio 与 Streamable HTTP？

stdio 通过父进程与子进程的 stdin/stdout 传协议，适合本地开发和桌面 Host。Streamable HTTP 适合未来远程服务，但需要认证、网络边界、限流和部署设计；v0.15-A 没有开放它。

## 如何证明只读？

Adapter 只调用现有只读 Coach Tool，Session 在 finally 中 rollback/close；测试拦截 INSERT/UPDATE/DELETE 并比较关键表行数。没有任何 MCP 写工具注册。

## 当前限制是什么？

没有远程认证、HTTP transport、Resources、Prompts、写工具、MCP 计划审批或 Multi-Agent。直接 stdio 启动默认没有身份，仅能发现工具。

