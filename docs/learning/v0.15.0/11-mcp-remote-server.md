# Remote MCP Server Operation

最小部署配置：

```dotenv
MCP_HTTP_ENABLED=true
MCP_HTTP_HOST=127.0.0.1
MCP_ALLOWED_ORIGINS=https://trusted-client.example
MCP_ALLOWED_HOSTS=mcp.example.com
MCP_TOKEN_ISSUER=gaitlogic-planner
MCP_TOKEN_AUDIENCE=gaitlogic-mcp
MCP_TOKEN_EXPIRE_MINUTES=30
```

生产环境应使用 HTTPS，并让反向代理只转发 `/mcp` 到应用；不要把运行目录、`.env`、数据库地址或调试端点公开。客户端必须每次请求都携带 Bearer Token，即使同一个 MCP session 已初始化。Token 过期后客户端需要重新使用受控 GaitLogic 登录流程获取新 Token。

若 `MCP_HTTP_ENABLED=false`，主应用不挂载 MCP HTTP 端点，现有 REST 与 stdio 行为不变。Origin 被拒绝、Token 无效或用户停用时，工具不会执行。当前远程模式没有 OAuth Discovery、DCR、refresh token、Resources 或 Prompts；不要把它暴露给不受控公网客户端。
