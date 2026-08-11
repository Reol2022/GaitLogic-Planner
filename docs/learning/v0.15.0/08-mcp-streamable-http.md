# MCP Streamable HTTP

v0.15.0-B 在现有 stdio Server 之外，增加了远程端点 `/mcp`。它使用 MCP Python SDK 2.0 的 `MCPServer.streamable_http_app`，由 SDK 负责 JSON-RPC、初始化、会话 ID 和 Streamable HTTP 的 POST/GET 生命周期；GaitLogic 不手写协议，也没有继续使用旧的 HTTP+SSE-only 教程。

Streamable HTTP 与 stdio 的区别在于：stdio 是 Host 启动本地子进程后，通过 stdin/stdout 传输 MCP 消息；HTTP 是独立进程服务多个客户端。stdio 的 stdout 只能包含 MCP 消息，日志走 stderr。HTTP 的每一个请求都要经过 Origin 与身份校验。

应用仅在 `MCP_HTTP_ENABLED=true` 时挂载 `/mcp`。默认关闭，示例配置的 Host 和 Origin 都是 localhost。部署进程本身仍应由 Uvicorn、Supervisor 或反向代理显式绑定到受控地址；`MCP_HTTP_HOST` 用于 MCP SDK 的本地安全配置，不能替代网络层的绑定与 TLS 配置。

远程 MCP 与 `/api/...` REST 路由分离：REST 继续服务产品 UI，`/mcp` 只处理 MCP 协议。当前不支持 Resources、Prompts、写工具、旧 SSE-only transport 或远程 Provider 代理。
