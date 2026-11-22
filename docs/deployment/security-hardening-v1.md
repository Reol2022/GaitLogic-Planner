# Security Hardening v1

日期：2026-11-19。状态：本地开发与隔离验收，未提交、未推送、未部署。该文档不证明线上安全组、Nginx 或应用防护已经生效。

测试证据：[本地验收报告](../evaluation/security-hardening-v1.md)。

## 范围和基线

基于本地 HEAD `ec6f7d6` 创建 `codex/security-hardening-v1`，保留已有 MCP v3.4、同步一致性、后台设置和审计工作区。未修改受保护的 `scripts/upgrade_v0130_adaptive_plan.py` 或用户架构图。未连接生产数据库、未更换密钥、未触发 Garmin 同步或付费模型。

本批建立应用层请求准入，不是 WAF、DDoS 清洗、完整会话撤销或所有历史安全债务的修复。模型 Token 上限和已有成功草稿额度继续生效；新计数是请求尝试预算，不是按实际账单结算的货币额度。

## 实现

| 控制 | 位置 | 行为 |
| --- | --- | --- |
| Web/MCP 信任域隔离 | `server/services/auth_service.py` | 新 Web JWT 使用 `purpose=web`、`iss=gaitlogic-web`、`aud=gaitlogic-web-api`，校验算法、类型、到期时间和有界数字主体；MCP audience/resource/revocation 不改变。 |
| IP 与管理来源 | `server/security/middleware.py` | 只使用 ASGI client，不自行信任 XFF；配置后限制 `/api/admin*`，管理员身份仍须数据库验证。IPv6 频率键按 /64 合并。 |
| 共享速率计数 | `server/security/admission.py` | MySQL upsert + 行锁 + 短事务；账户 ID、来源和用户策略使用带命名空间的 HMAC 键，不存原始账号/IP。 |
| AI 并发 | 同上与 `server/api/deps.py` | 已认证用户进入 Coach、AI Plan、复盘生成/graph/方案修订前申请用户级和全局租约；请求期间续租，成功/异常/取消释放，崩溃后过期恢复。模型调用期间不持有数据库锁。 |
| MCP | `server/mcp/http.py` | 验证 grant、撤销状态和账号之后检查用户请求预算，知识调用另有预算；恢复 scope 仍在健康事实读取前检查；认证查询完整放在线程中获取/释放 Session。 |
| 文件和请求体 | `server/security/uploads.py` | 一般请求最多 10 MiB，认证/OAuth 64 KiB；请求体在 JSON/multipart 解析前有界读取，缺 Content-Length 同样受限。文件内容最多 2 MiB；Excel 压缩成员、展开大小、比例、路径、宏、DTD/实体及行列受限。 |
| 安全错误 | `server/common/exceptions.py` | 429 携带 Retry-After；SQL/通用异常不记录异常正文/参数，校验错误不回显 input/context；主业务 engine 隐藏参数。 |
| 前端 | `web/src/api/request.ts` | 展示合法 Retry-After 与服务端安全提示，不自动重试、不清除有效登录。 |

原来的 Coach 进程本地计数、AI Plan 成功额度、Conversation lease、同步 lease、OAuth scope 与 HITL 不删除。新增门控是外层保护，不能把已有成功草稿额度当作付费请求尝试总量限制。

登录采用源 IP、真实数据库账号 ID 和账号+来源三层尝试限制；不存在的账号使用归一化名称的 HMAC。成功登录不会清空尝试计数，避免成功/失败混合请求绕过预算。达到阈值是临时等待，不永久停用用户；共享校园网需观察实际流量后调参。

## 默认策略（启用总开关后）

| 策略 | 默认上限 | 作用域 |
| --- | --- | --- |
| 普通 API/受保护 MCP HTTP | 300 / 60s | 来源 IPv4 或 IPv6 /64 |
| 登录提交 | 60 / 60s | 来源 |
| 登录账号 | 30 / 900s | 账号，跨来源共享 |
| 登录账号+来源 | 8 / 300s | 组合 |
| 注册 | 5 / 3600s | 来源 |
| OAuth 路由 | 60 / 60s | 来源 |
| Coach 与复盘模型入口 | 6 / 60s、100 / 86400s | 用户，共享 |
| AI Plan 请求 | 6 / 3600s、12 / 86400s | 用户，原有成功额度仍独立执行 |
| 同步 POST | 12 / 3600s | 用户，后台调度不使用浏览器请求预算 |
| 导入 POST | 10 / 3600s | 用户 |
| MCP 已认证 HTTP | 120 / 60s | 用户，跨 scope/令牌共享 |
| MCP 知识检索 | 30 / 60s | 用户 |
| AI 并发 | 每用户 1，全局 10 | 同时执行的 HTTP 请求 |

这是首次使用时开始的有界时间窗，不是滑动窗口，也不是自然日额度。失败、缓存命中、重复请求等均可消耗请求预算，但不因此扣除成功草稿额度。被并发门控拒绝的请求可能已消耗尝试预算，避免高频重试风暴。状态轮询 GET 不计入 AI 请求预算，但受基础来源频率限制。

`SECURITY_RATE_LIMITS` 可覆盖策略数值，例如 `{"coach_minute":6,"coach_day":100,"ai_concurrency":1,"global_ai_concurrency":10}`；不接受未知键、非整数、零或负数。

## 数据库和迁移

新增两张基础设施表，ORM、`sql/schema.sql` 和初始化脚本保持一致：

- `security_rate_bucket(key_hash, count, expires_at)`，过期索引。
- `security_request_lease(token, gate_hash, expires_at)`，gate/expiry 复合索引。

不保存用户内容、密码、Bearer Token、健康事实或真实 IP。这些表是匿名/用户请求的共享安全状态，不对客户端提供读写接口。租约 token 是内部随机标识，不是用户登录凭据。

部署前备份，先在生产 Schema 的隔离副本预演。以下命令中的数据库名必须替换为已核实目标；本轮没有执行生产命令：

```powershell
python -m scripts.upgrade_security_hardening_v1 --database EXACT_VERIFIED_DATABASE
# 审核目标、备份和预演结果后，单独授权执行：
python -m scripts.upgrade_security_hardening_v1 --database EXACT_VERIFIED_DATABASE --apply
```

迁移只增加安全表，不删除旧业务结构。MySQL DDL 不保证整体回滚；中断后可重复执行以建立剩余表。已存在但字段不符合预期时停止，不能直接删表重建。后续用 `--prune` 有界清理超过一天的过期计数/租约，每次最多各 1000 条，保留仍有活跃租约的 gate；按实际规模安排维护任务，不自动创建线上定时任务。

## 发布和启用顺序

1. 保留备份和旧发布目录，完成隔离迁移、旧业务及 OAuth 回归。
2. 合并/推送/上传/部署均需另行授权；本批不执行这些动作。
3. 核实后端只监听本机地址。安全组仅公网开放网站所需 80/443；SSH/宝塔限管理来源，数据库及缓存不公开。不要先关闭当前 SSH 通道。
4. 先迁移两张安全表，再配置 `SECURITY_CONTROLS_ENABLED=true`。缺表、锁失败或安全数据库不可用时受控入口返回 503，不回退到每进程限流。`GET /api/health` 保持独立于安全数据库的 liveness 语义，不代表数据库 readiness；其边缘限流仍由 Nginx 负责。
5. 用已核实的管理员公网 IP/CIDR 配置 `SECURITY_ADMIN_ALLOWED_IPS`。空值不启用管理 IP 限制；不知道管理 IP 时不要猜测，先保留控制台应急登录手段。
6. 在 Nginx `http {}` 审查合入 [限流区模板](../../deploy/nginx-security-http.conf.example)，在现有站点审查合入 [server 模板](../../deploy/nginx-security-server.conf.example)。不要复制替换宝塔现有站点或重复声明相同 location。先 `nginx -t`，修改和 reload 均需授权。
7. Nginx 应覆盖客户端传入的 XFF；Gunicorn/Uvicorn 的代理信任仅限真实反向代理，禁止 `FORWARDED_ALLOW_IPS=*`。存在 CDN 时先核验其真实地址恢复配置。本应用不能识别已经被错误代理配置伪造的 ASGI client。
8. MCP/OAuth/metadata 继续经 HTTPS 443，保留 Authorization、Host、协议及路径；MCP 禁用缓存/响应缓冲。TLS 证书必须匹配域名，不关闭验证；生产只启用适用的 TLS 1.2/1.3 配置。
9. 新版本默认拒绝旧的无用途 Web JWT，需要重新登录。若确需平滑迁移，只能设置明确带时区的 `WEB_TOKEN_LEGACY_UNTIL` 绝对截止时间，到期删除配置；兼容窗口从不接受 MCP-shaped Token。不得把“保持旧令牌永久有效”当作兼容方案。
10. 验证正常登录、错误密码限流、管理来源拒绝、Coach 与 Plan 并发拒绝、MCP 初始化/工具/恢复 scope、同步排队、导入和移动端错误提示。429 应有 Retry-After，前端不能无限自动重试。

## 回滚

- 新保护出现误限流时先核实策略和代理来源；按需调整具体策略，不全局信任转发头。
- 若必须紧急关闭新增门控，`SECURITY_CONTROLS_ENABLED=false` 仅撤销新增准入与 IP 白名单，不关闭 JWT、用户权限、MCP OAuth、同步租约或 HITL。这会失去新增流量保护，须保留边缘限流并明确记录风险。
- Web/MCP 信任域修复、日志与文件保护不随总开关关闭。回退到旧代码会重新暴露已确认的边界问题，不作为常规回滚选择。
- 不删除两张安全表；保留当前请求状态用于诊断。旧代码版本是否能识别新 Web JWT 必须在预演中验证，不保证所有历史版本兼容。

## 尚未解决

- 现有 logout 仍不是服务端 Web 会话撤销；改密/全端退出的统一会话策略留待下一批。
- 不提供永久 IP 封禁、验证码、MFA、WAF 或 DDoS 清洗。应用数据库限流不能替代 Nginx/安全组；大量来源的攻击仍可能给安全状态表带来压力。
- 没有新增统一的 Provider 账单/实际 Token 原子结算；内部脚本绕过 HTTP 的调用不自动受请求级门控保护。必须继续遵守现有模型调用次数、上下文/输出上限和 Provider 超时。
- 租约依赖数据库续租；超过租约期限的持续数据库故障与进程停顿可能降低并发上限保证。新请求在数据库不可用时拒绝，未实现分布式 fencing 或远端 Provider 强制取消。
- 文件安全限制不是对 PDF/Word 等所有未来解析器的沙箱保证；当前覆盖三个既有 Excel/计划/活动导入入口。未实施硬 CPU/内存隔离或所有服务日志的全面脱敏。
- 未做生产容量压测、真实账号认证或生产 Nginx 语法检查；示例不是已生效的服务器配置。

## 参考

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)：账号维度与来源维度的登录保护及可用性权衡。
- [Uvicorn Settings](https://uvicorn.dev/settings/)：代理头只信任指定来源。当前代码仍以项目锁定依赖和本地测试为准，没有升级框架/SDK。
