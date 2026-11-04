# Remote MCP 上线准备（未就绪）

当前仅为部署准备，禁止将以下建议直接用于生产。生产实际提交、域名、站点配置、数据库结构和依赖版本尚未取得，不能确认 MCP 可单独部署；需要先比较生产部署提交与本地目标提交，以及 OAuth 表和训练服务依赖的迁移。不要把含其他未验收功能的整个开发分支直接覆盖生产。

v0.3.1 已开始实现 resource 绑定及数据库授权撤销，但尚未完成隔离 MySQL 安全验收。`scripts/upgrade_mcp_oauth_security.py` 被刻意限制为本机测试库，不是生产迁移指令；上线前仍需制定和验证独立迁移及回滚方案。旧令牌、授权码及刷新令牌需要重新授权。

v0.3.3 已在受限本机 MySQL 中验证部分 DDL 后重试、两个资源间令牌重放拒绝、双用户 TCP 工具调用、刷新竞争及重启后撤销。旧表迁移的本机链路已通过；不代表生产数据迁移或恢复已验收。`MCP_RESOURCE_URI` 应配置为实际的、经 TLS 验证的 MCP URL；OAuth issuer 由可信 `MCP_PUBLIC_BASE_URL` 的 `/oauth` 路径确定。变更这两项会令旧授权需要重新建立。

## 上线阻塞项

1. 实现并在隔离 MySQL 验证 OAuth canonical resource 的授权、令牌兑换和受众绑定；当前只验证内部配置的 JWT audience，不能等同于资源绑定。
2. 实现和验证按用户、客户端撤销 access token 与 refresh token，以及轮换重放处理和重启持久性；当前 JWT 无即时撤销。
3. 完成合成双用户 OAuth HTTP E2E、真实双用户隔离、训练数据逐条一致性和并发测试。
4. 核验生产域名 DNS、SNI、证书链与有效期，现有建议域名的证书主机名校验失败；确认该域名是否实际使用。
5. 审查 OAuth 登录及客户端注册的限流、审计和代理日志脱敏，确认健康信息的授权边界。

## 升级路径比较

| 方案 | 优点 | 未知与风险 |
| --- | --- | --- |
| 整体升级当前开发版本 | 依赖及领域代码按同一版本运行 | 生产提交未知；Coach、Garmin Recovery、数据库迁移和依赖差异均须完整回归，回滚影响面较大。 |
| 提取 MCP 最小兼容补丁 | 有机会缩小变更范围 | MCP 依赖共享训练服务、身份认证、OAuth 表、MCP SDK 和 FastAPI 生命周期，尚未对实际生产版本验证补丁兼容。 |

在取得生产版本和只读配置之前，无法可靠认定哪条路径风险最低。先构建可复现的生产版本副本并验证最小补丁；如果依赖链无法独立满足，再评估整体升级。生产密码、密钥和令牌不得纳入部署文档。

## 最小只读服务器检查

在实际部署目录执行：`git rev-parse HEAD`、`git status --short`、`python --version`、`python -m pip show mcp`；通过宝塔面板或 `nginx -T` 检查生效的站点配置。输出前删除密码、密钥、完整令牌、数据库连接串和隐私字段。使用 `openssl s_client -connect <实际域名>:443 -servername <实际域名> -verify_return_error` 核验证书链与 SNI，再检查证书 SAN 和有效期；不得关闭 TLS 验证。

只报告以下环境变量是否设置和非敏感语义，不要输出值：`MCP_HTTP_ENABLED`、`MCP_OAUTH_ENABLED`、`MCP_PUBLIC_BASE_URL`、`MCP_ALLOWED_HOSTS`、`MCP_ALLOWED_ORIGINS`、`MCP_OAUTH_ALLOWED_REDIRECT_HOSTS`、`MCP_TOKEN_ISSUER`、`MCP_TOKEN_AUDIENCE`、签名密钥配置。现阶段 `MCP_TOKEN_AUDIENCE` 不等于已完成 canonical resource 绑定。

## 部署设计与核验

完成安全修复后，根据实际 Nginx 配置分别代理 `/mcp`、`/oauth/` 和 `/.well-known/`，保留 Host 与 Authorization，确认 HTTPS 元数据地址、回调白名单、流式超时和缓冲；只信任受控代理的转发头。先备份经验证可恢复的应用、配置及数据库，记录原版本、依赖、环境变量与迁移状态；上线前拟定按原版本恢复代码、配置和数据库的具体操作，并演练 `nginx -t` 与服务回滚。

部署后分别验证原 Web/API、无令牌拒绝、OAuth discovery、PKCE、重启后授权状态、工具调用、双用户隔离及日志脱敏。失败时执行已演练的回滚。以上均未执行。
