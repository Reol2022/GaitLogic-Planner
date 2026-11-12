# Remote MCP 部署记录与上线准备

## 恢复数据补充授权（2026-11-12）

- `mcp:read` 和 `mcp:recovery:read` 仍为独立权限，不迁移或批量扩充既有令牌。
- 新授权页面为基础权限请求提供默认未勾选的恢复数据选项；明确请求恢复权限时仍要求单独同意。授权码记录用户实际同意的范围，Token 响应返回实际 scope。
- OAuth 远程恢复调用缺少 scope 时返回 HTTP 403、`WWW-Authenticate: Bearer error="insufficient_scope"`、完整所需 scope 与固定资源 metadata 地址。直接工具适配器仍保留查询前权限检查，不信任客户端工具名称请求头。
- 客户端支持补充授权时可按挑战重新发起 OAuth。不支持时，断开并重新连接 GaitLogic，在授权页勾选恢复数据选项。不通过刷新旧 Token 自动提权，不手动修改 JWT 或数据库 scope。
- 不需要数据库迁移。更新代码并重载后端即可；需用户重新授权才能验证其真实恢复查询。健康检查、权限提示或合成数据验收不能代替用户实际同意。
- 协议依据：[MCP Authorization / Scope Challenge Handling](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization#scope-challenge-handling)、[OAuth 2.0 scope response](https://www.rfc-editor.org/rfc/rfc6749.html#section-3.3)。

## 2026-11-10 线上增量

- 应用版本0.16.8，MCP版本 `0.16.8-facts-v3.2` 已通过最小补丁上线。代码改动限于server/mcp的七文件及knowledge_retrieval/index_service.py，不包含本地未部署AI课表修改。
- 先核对当前目录、校验压缩包、备份代码，再平滑重载Gunicorn；失败时按备份回滚。不修改数据库或OAuth授权状态。
- 公网未授权请求仍为401，带正确OAuth metadata挑战和新版本响应头，后端健康正常。
- 通过既有授权连接确认新版本、7/28天已完成次数对齐，以及旧式截断请求返回游标。
- RAG重建的数据流授权、暂存验收、备份切换和真实MCP查询均已完成。当前宿主仍为旧四工具定义，客户端刷新六工具定义尚待完成。

### 本次 RAG 发布与回滚

- 当前发布目录为 `20261109-a78e773b`；此次是增量文件补丁，不把目录中的历史commit名视为当前全部代码内容的精确Git证明。
- 已授权的52篇公开训练知识、304个分块只发送至既有Embedding服务，Qdrant为127.0.0.1。新索引ID见验收报告；Dense策略、OAuth和数据库未变更。
- 暂存就绪检查及两条Canonical引用查询通过后，备份语料manifest、原索引构建源码和shared环境文件，复制新immutable索引目录，仅更新Dense/BM25索引ID。旧索引/集合未删除。
- 备份位于 `shared/deployments/mcp-rag-v32-retry1/backup`，部署回执位于同级safe-receipt.json。environment.private仅root可读，绝不提交Git或作为公开附件。首次失败尝试另保留mcp-rag-v32备份。
- 经验：Gunicorn以www运行。.env原子替换必须保留所有者/组及读取权限；本次采用root:www、0640。备份保持0600。禁止把生产.env设为root:root、0600后直接重载。使用实际服务用户执行就绪检查，避免root检查通过但worker无法读取。首次权限错误已回退恢复，之后重试通过。
- 发生回归时，管理员先核对current与备份对应的release，恢复manifest、构建源码及environment.private到shared/.env，恢复root:www/0640权限；不要覆盖其他环境变更。新目录可保留为未启用索引，不删除旧集合。核对实际Gunicorn主进程及cwd后重载；主进程不在则通过已核实的宝塔项目启动。随后检查/api/health、未授权/mcp的401及授权知识查询。不要盲用历史PID。
- 最终www就绪检查PASS、后端健康200；真实连接两次知识检索SUCCEEDED且各有3条Canonical引用。数据库和Garmin同步均未执行。

### RAG恢复及未来发布要求

1. 仅使用已有训练知识语料，不将聊天、训练日志、健康详情或凭据作为索引输入。
2. 审查语料变化，在独立目录重建清单及新版本索引。使用已有受信任Embedding配置，语料外发先取得明确授权。
3. 暂存检索、Canonical引用和就绪检查通过后，备份原清单、索引与配置，再发布匹配索引ID。
4. 保留旧索引及配置，重载后从真实MCP连接验收，不以构建成功替代工具可用。
5. 后续发布必须携带匹配的语料、清单及私有运行时索引。scripts/deploy.ps1普通代码包未包含knowledge和var索引，不能单独完成RAG迁移。
6. 不把向量或索引提交Git，不放宽路径安全检查来接受任意共享目录软链接。使用受支持的发布目录内路径并校验哈希。

## 以下为历史部署准备记录（2026-11-04）

当前仅为部署准备，禁止将以下建议直接用于生产。生产实际提交、域名、站点配置、数据库结构和依赖版本尚未取得，不能确认 MCP 可单独部署；需要先比较生产部署提交与本地目标提交，以及 OAuth 表和训练服务依赖的迁移。不要把含其他未验收功能的整个开发分支直接覆盖生产。

RC `64b04eb` 已实现 resource 绑定和数据库授权撤销，并完成部分隔离 MySQL 与本机 TCP 安全验收。`scripts/upgrade_mcp_oauth_security.py` 被刻意限制为本机测试库，不是生产迁移指令；上线前仍需制定和验证独立迁移及回滚方案。旧令牌、授权码及刷新令牌需要重新授权。

v0.3.3 已在受限本机 MySQL 中验证部分 DDL 后重试、两个资源间令牌重放拒绝、双用户 TCP 工具调用、刷新竞争及重启后撤销。旧表迁移的本机链路已通过；不代表生产数据迁移或恢复已验收。`MCP_RESOURCE_URI` 应配置为实际的、经 TLS 验证的 MCP URL；OAuth issuer 由可信 `MCP_PUBLIC_BASE_URL` 的 `/oauth` 路径确定。变更这两项会令旧授权需要重新建立。

## 上线阻塞项

1. 复核生产 canonical resource、issuer 与 TLS 地址；RC 已完成本地资源绑定测试，生产尚未验证。
2. 在生产版本副本验证 grant 表持久化、授权撤销、刷新重放及重启行为；RC 的隔离 MySQL 已覆盖部分场景。
3. 完成真实账号训练数据逐条一致性及生产环境隔离验收；RC 已通过合成双用户 TCP 和并发测试。
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

只报告 MCP 环境变量是否设置，不要输出值。RC 的 JWT issuer 由 `MCP_PUBLIC_BASE_URL` 的 `/oauth` 路径确定，audience 绑定 `MCP_RESOURCE_URI`；不要将旧的 `MCP_TOKEN_AUDIENCE` 当成当前资源配置。

### 只读检查脚本

在宝塔终端进入实际后端目录后，可使用 [mcp_production_readonly_audit.sh](../../scripts/mcp_production_readonly_audit.sh)。脚本不输出进程参数、环境变量值、原始 Nginx 配置或用户数据；部署目录、Python 路径和域名需由管理员先核实。

```bash
GAITLOGIC_AUDIT_PYTHON='<实际 Python 路径>' \
GAITLOGIC_AUDIT_DOMAIN='<已确认域名>' \
GAITLOGIC_AUDIT_ENV_FILE='<实际环境文件路径>' \
bash /path/to/mcp_production_readonly_audit.sh
```

脚本路径和变量中的占位符必须替换，不确定时可省略相应变量。MySQL 元数据检查需使用既有的只读 MySQL login-path，并额外设置 `GAITLOGIC_AUDIT_DB` 和 `GAITLOGIC_AUDIT_MYSQL_LOGIN_PATH`；仅查询 `information_schema`。请先审阅输出，移除不希望公开的域名和内部路径，再反馈脱敏结果。不要上传 `.env`、完整 `nginx -T`、令牌、密码或数据库连接串。

2026-11-04 当前网络的只读检查：`gait.reol2020.cn` TLS 校验通过且首页 HTTP 200；`back.reol2020.cn` 出现证书主机名不匹配。后者是否承担生产 API 尚未确认，不能据此替换域名或关闭校验。

## 部署设计与核验

完成安全修复后，根据实际 Nginx 配置分别代理 `/mcp`、`/oauth/` 和 `/.well-known/`，保留 Host 与 Authorization，确认 HTTPS 元数据地址、回调白名单、流式超时和缓冲；只信任受控代理的转发头。先备份经验证可恢复的应用、配置及数据库，记录原版本、依赖、环境变量与迁移状态；上线前拟定按原版本恢复代码、配置和数据库的具体操作，并演练 `nginx -t` 与服务回滚。

部署后分别验证原 Web/API、无令牌拒绝、OAuth discovery、PKCE、重启后授权状态、工具调用、双用户隔离及日志脱敏。失败时执行已演练的回滚。以上均未执行。
