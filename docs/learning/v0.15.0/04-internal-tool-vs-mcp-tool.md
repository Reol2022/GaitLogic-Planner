# 内部 Tool Calling 与 MCP Tool 的区别

Coach Agent 的内部 Tool Calling 是应用内编排：`AgentToolRegistry` 根据 Intent Policy、可信用户身份和模型调用流程执行受限工具。它服务于本系统的 Coach API。

MCP Tool 是跨应用协议能力：它让可信 Host 能发现和调用一个明确的公开能力。MCP 不替代内部 Tool Policy、Runner State、训练规则、Validator 或 Fallback；在本项目中 MCP 反而复用内部 Registry，避免形成第二套“训练事实”。

因此，即使未来接入一个 MCP Client：

- MCP 不能绕过身份注入；
- MCP 不能声明自己要读哪个用户；
- MCP 不能改变 TODAY 的确定性决策；
- MCP 不能写训练计划或日志；
- MCP 不会自动拥有 Resource、Prompt、审批或 Agent 权限。

这种分层保留了既有安全边界，也使同一业务计算在 Coach 和 MCP 中保持一致。

