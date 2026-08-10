# MCP 是什么

Model Context Protocol（MCP）是 Host、Client 和 Server 之间的开放协议。Host 是用户实际使用的应用，Client 负责协议连接，Server 声明可调用的能力。MCP Server 可以提供 Tool、Resource 和 Prompt；它们是不同的协议能力，不能混为“一个聊天 API”。

本项目 v0.15-A 使用 MCP Python SDK 2.0.0。本地验证使用当前 SDK 的 `mcp.server.mcpserver.MCPServer` 与 `mcp.Client`；没有采用旧版 FastMCP/SSE 教程的导入路径。官方 SDK 还支持内存 Client，所以协议测试不需要真实 Claude、Cursor 或外网模型。

本阶段只实现 Tool：一次带严格参数的只读调用，并返回结构化结果。Resource、Prompt 和采样功能未注册。stdio 是本地子进程的标准输入输出传输：stdin 接收 JSON-RPC，stdout 只发送协议消息；普通日志不能写 stdout。Streamable HTTP 是面向未来远程部署的传输选择，但 v0.15-A 不启用它。

