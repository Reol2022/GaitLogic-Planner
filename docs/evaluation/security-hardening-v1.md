# Security Hardening v1：本地验收

> 发布补记（2026-11-22）：代码 `3e4a00a` 已部署；备份后完成两表迁移及重复执行，应用限流已启用。登录 429、Web/MCP 信任域隔离通过；Nginx、防火墙与管理员 IP 白名单未变。下文保留开发阶段快照，实际发布证据见[发布验收](release-20261122.md)，不代表所有审计风险已解决。

日期：2026-11-19。分支 `codex/security-hardening-v1`，基线 `ec6f7d6`。状态：本地修改、隔离验收，未提交、未推送、未部署。原有未提交改动保留，不将当前全部 diff 归属本批。

## 本批修复和范围

| 原审计项 | 本地状态 | 证据和限制 |
| --- | --- | --- |
| A-01 认证信任域 | 已修复本批确认路径 | 新 Web/MCP 令牌双向拒绝，签名有效但用途/主体/类型错误仍拒绝；真实 MySQL 用户停用在 AI 门控与模型执行前拒绝。生产尚未更新。 |
| A-02 通用异常日志 | 已修复通用处理路径 | SQLAlchemy 主 engine 隐藏参数；数据库/通用 handler 仅日志方法、路由模板及异常类别；合成 canary 不出现在日志和输入校验错误中。不宣称所有业务/Provider 日志均已审查。 |
| A-04 入口滥用保护 | 本地实现、默认未启用 | MySQL 共享 IP/账号/用户请求计数、AI 租约、MCP 用户/知识预算、管理来源限制。双进程测试验证预算共享；生产边缘规则未变。 |
| A-05 文件解析 | 本批三个既有导入入口已增加保护 | 上传有界读取、ZIP 展开/比例/成员/路径/宏/实体限制、Excel 行列预检；标准模板保留。不等于所有文档类型均已沙箱化。 |
| A-06 AI 并发/成本 | 请求层保护，部分完成 | HTTP AI 入口共享尝试上限、用户级与全局并发，保留原有成功额度/幂等/审批；未实现所有内部 Provider 调用的实际 Token/货币原子结算。 |
| A-03 Web logout 撤销 | 未修复 | 仍须单独设计会话撤销、改密与全端退出。 |
| P-01 混合并发停滞 | 未重新验收 | MCP 身份查询移至线程，完整混合负载 50 VU 未重跑；不能宣称系统吞吐/容量问题已解决。 |

## 文件

- 配置：`planner_core/config.py`、`.env.example`。
- 共享状态：`planner_core/database/models.py`、`sql/schema.sql`、`scripts/init_db.py`、`scripts/upgrade_security_hardening_v1.py`。
- 准入及文件保护：`server/security/{admission,middleware,uploads}.py`，不引入 Redis 或新依赖。
- 认证接入：`server/services/auth_service.py`、`server/schemas/auth.py`、`server/api/deps.py`、`server/api/routes/{auth,mcp_oauth}.py`、`server/mcp/http.py`、`server/main.py`。
- 日志：`server/common/exceptions.py`、`planner_core/database/session.py`。
- 导入：三个路由 `excel/plan_imports/workout_imports` 及对应服务，保留正式业务校验和用户隔离。
- 前端：`web/src/api/request.ts`、对应 Vitest。
- 测试：`tests/test_security_hardening.py`、`tests/test_security_hardening_mysql.py`；隔离运行器只增加对应测试库族的受限授权选项。
- 部署：[Runbook](../deployment/security-hardening-v1.md)、`deploy/nginx-security-*.conf.example`。未安装到服务器。

## 真实执行环境

Windows、本地 Python 虚拟环境、MySQL 8 loopback:3307；随机 `gaitlogic_test_*` 数据库和临时受限账号。管理连接仅负责创建/删除已验证名称的测试库及账号；测试进程无生产库权限。所有用户、凭据标记、归属和活动均为合成输入。双进程测试使用 spawn 独立解释器/独立 SQLAlchemy 连接，不是仅模拟方法调用。

没有生产扫描、生产写入、真实 Garmin 同步、真实用户健康资料或付费 LLM 请求。不是压力测试或生产性能基线。

## 测试结果

| 分组 | 结果 | 说明 |
| --- | --- | --- |
| 安全 MySQL/单元、MCP HTTP/OAuth routes、OAuth MySQL/真实 TCP、同步一致性 | 75 passed / 0 failed / 0 skipped，36.00s | 包含实际 MySQL 原子预算、双进程共享、租约过期与迟到释放、异常/取消释放、管理 IP、chunked 超限、数据库不可用、MCP 恢复权限与知识限流、幂等迁移/部分表恢复/清理。 |
| Coach 查询、AI 输出/额度/反馈、Excel 模板/解析、Required Facts、API 结构 | 72 passed / 0 failed / 4 skipped，10.74s | 初轮 AI Plan 4 项因未注入本地隔离连接跳过；不得算作通过。 |
| AI Plan 缓存与额度补跑 | 4 passed / 0 failed / 0 skipped，24.66s | 使用受限测试库族完成缓存、冷却、每日额度及缓存只记一次的真实数据库回归。 |
| 最终 MySQL 安全专项复跑 | 12 passed / 0 failed / 0 skipped，7.06s | 在清理条件补充并发安全的过期时间复核后重跑，和上述集成分组存在交集。 |
| 前端错误提示与同步组件 | 12 passed / 0 failed | 含 Retry-After 展示，不自动重试或错误清除会话；存在既有 Element Plus 测试 stub 提示。 |
| Typecheck | PASS | vue-tsc。 |
| 前端构建 | PASS，10.73s | 存在既有大包及第三方注释警告，无构建失败。 |
| MCP 独立 SDK tools/list | PASS | 六个工具输入/输出兼容检查通过，无新增工具。 |
| 生产 Nginx/防火墙与迁移 | NOT EXECUTED | 仅准备模板及步骤，未进行线上操作。 |
| `git diff --check` | PASS | 受保护的无关迁移脚本 SHA256 保持不变，无差别暂存未执行。 |

分组存在交集，不相加宣称唯一用例总数；未执行全仓 pytest。最初新增单元测试使用了当前环境未安装的异步测试插件及过长参数 ID，已改为标准 asyncio 驱动和固定用例 ID后重跑通过；没有删除失败案例。

## 上线条件

本地实现可进入发布审查，不等于生产已具备防护。正式上线前必须：

1. 确认管理员来源 IP/CIDR 和可信反向代理；不要使用所有 IP 管理白名单或任意 XFF。
2. 备份并对生产 Schema 的隔离副本预演安全表迁移；另行授权生产 DDL。
3. 审查合入 Nginx 限流、连接/体积/超时模板，核验 `nginx -t`；另行授权修改及 reload。
4. 建表后启用 `SECURITY_CONTROLS_ENABLED`，否则新增准入不会生效。空管理来源配置也不会启用 IP 白名单。
5. 确认旧 Web JWT 重新登录策略或明确截止的兼容窗口；MCP grant、scope、撤销和审批仍严格保留。
6. 在授权发布后复测 Web/MCP/OAuth、原有导入、训练读取与同步，不以本地测试代替生产验收。

完整策略、迁移、回滚及未解决风险见 [部署文档](../deployment/security-hardening-v1.md)。
