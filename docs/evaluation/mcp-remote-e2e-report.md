# Remote MCP：端到端验收与部署审计

记录日期：2026-11-04。该报告不包含用户训练明细、授权令牌或数据库凭据。

## v0.3 进展

## v0.3.1 安全开发进展（尚未完成验收）

## v0.3.2 合成 MySQL / TCP 补充验收

## v0.3.3 最终补充（2026-11-04）

## Release Candidate 补充验收（2026-11-04）

- 受限本机 MySQL 测试账号下，MCP 安全与业务回归 **53 passed，0 skipped**。使用全新历史 Schema 隔离数据库，依次执行部分 DDL 恢复、两次迁移及迁移后双用户 TCP OAuth／训练读取、刷新竞争和撤销，**3 passed，0 skipped**。
- 随后在同一已迁移库扩充真实 TCP 验证：分别构造旧 issuer/audience 的签名 access token、缺少 grant 的签名 token 和缺少 resource/grant 的旧 refresh 记录，均遭拒绝；本次扩展回归 **2 passed**。
- 真实 TCP 测试中，A 的 access token 无法用于 B；A 的 refresh token 无法为 B 换取 token；授权与兑换资源不一致、授权码重复兑换、无 grant 旧 access token 和无绑定旧 refresh token 均被拒绝。伪造 Host 与 X-Forwarded-Host 未改变配置的资源判定。
- 历史迁移测试保留旧授权记录，先模拟一个 DDL 已提交的部分升级，再重复运行迁移；后续网络 E2E 在相同迁移库创建新授权并完成调用和撤销。旧 token 使用合成旧格式验证，非真实生产 token。未强制中断数据库进程，不能将此描述为原子回滚。
- 7 天和 28 天合成查询、用户隔离、超过 20 条截断及训练服务 28 天字段对照通过；同一时点真实页面 API 对照仍 BLOCKED。空窗口及明细矛盾有合成测试，但尚未全部经独立网络客户端对照页面 API。
- 本机合成 33 次调用 p50 76.81 ms、p95 541.33 ms，仅为局部验证。生产实际提交、域名和 Nginx 尚未核实；未执行生产迁移、部署或 ChatGPT 实际连接。

- 两个不同资源标识对应两个本机 TCP MCP 服务；资源 A 令牌访问资源 B（包括伪造转发 Host）被拒绝。授权 A 后以错误 resource 兑换、授权码重放及跨 resource 刷新被拒绝；错误 audience 和缺少 grant 的旧令牌由独立 HTTP 安全测试覆盖。
- 使用历史 `86831ad` OAuth DDL 建立独立空 MySQL 库，先模拟一项 DDL 已提交的中断状态，再执行迁移两次；旧记录保留、授权表及唯一索引建立。随后在同一数据库通过真实 TCP 完成新用户授权、调用训练工具、撤销与重启复验。此方法验证部分升级状态可恢复；未强行终止运行中的 DDL 进程，也未证明 DDL 事务可回滚。
- 受限数据库账号运行的相关回归 **53 passed，0 skipped**；旧库升级并在该库执行双用户 TCP 和 MySQL 安全测试另 **3 passed，0 skipped**。一次合成 33 次工具请求 p50 78.53 ms、p95 538.16 ms。测试账号已删除；隔离测试数据库保留。
- 7 天和 28 天合成窗口、截断、来源和用户隔离已覆盖；28 天 MCP 明细与 Training Service 的记录引用、日期、距离、时长和来源完成比对。页面后端 API、空窗口与真实账号同时间点页面逐条对照仍未完整验收，不能声称全部数据一致性通过。
- 生产仍未就绪：迁移脚本明确限本地隔离库，尚无经验证的生产迁移和回滚；真实生产域名、TLS、Nginx、部署版本、日志脱敏及 ChatGPT 接入尚未核实。

- 使用本机 `127.0.0.1:3307` 的 `gaitlogic_test_mcp` 与临时受限测试账号；确认该账号无法读取其他业务库。临时账号在测试结束后删除，测试库保留。单独创建 `gaitlogic_test_mcp_migration_v032` 用于历史 Schema 迁移；数据库中仅有合成测试结构及记录。
- 双用户通过真实本机 TCP / Uvicorn、OAuth 授权码 + PKCE 和 MySQL 读取各自训练。28 天 22 条测试中返回 20 条并标记截断，7 天返回 7 条；另一个用户只看到自身记录。20 次连续、10 次并发工具调用通过；服务重启后撤销用户的令牌仍被拒绝，另一用户仍可访问。
- MySQL 线程屏障测试验证同一 refresh token 两次并发兑换结果为一次成功、一次失败；随后重放撤销对应授权，另一用户不受影响。
- 历史 `86831ad:sql/schema.sql` 创建的旧 OAuth 表迁移两次通过，旧授权码数据保留，新 resource/grant 字段为空。尚未完整验证迁移后使用旧令牌及新授权的独立网络 E2E，也未模拟中途 DDL 失败；MySQL DDL 非事务性，失败后应检查表结构并重复运行迁移，切勿无备份在生产执行。
- 相关运行：MySQL TCP 与安全测试 2 passed；历史迁移独立测试 1 passed；整组回归另一次 52 passed。一次合成 33 次工具调用的测量 p50 76.63 ms、p95 543.11 ms；只代表本机测试环境，不代表生产吞吐或延迟。
- Resource 的正确路径和错误 resource 已覆盖本地 MySQL 授权测试，错误 audience、旧无 grant 令牌和授权存储故障拒绝有合成测试；尚需补齐所有跨资源和迁移后旧令牌的真实 TCP E2E。生产与 ChatGPT 仍 NOT READY。

最终重跑：受限临时测试账号、隔离 MySQL、真实 TCP 双用户和相关回归合计 **53 passed，0 skipped**；另行在空隔离库从历史 DDL 执行旧版迁移测试 **1 passed**。真实 TCP 中额外覆盖错误 resource 兑换、授权码重复兑换和工具参数伪造用户 ID。MCP 明细与同用户训练服务对照验证了 record_ref、日期、来源、距离和时长；未验证用户界面页面。一次 33 次合成调用的本机测量 p50 77.86 ms、p95 559.31 ms。结果不是生产性能。

补充：刷新令牌并发测试随后扩展为三条同时请求：同一用户同一旧令牌竞争两次，另一用户独立轮换一次；结果为前者一次成功一次失败，后者成功。该独立 MySQL 测试重跑 1 passed。

- 已新增可配置 `MCP_RESOURCE_URI`；若未设置，使用可信的 `MCP_PUBLIC_BASE_URL` 加 `/mcp`。授权、令牌兑换和刷新必须提供相同 resource，授权码及刷新记录保存 resource，JWT audience 绑定该资源，旧记录需重新授权。
- 新增 `mcp_oauth_grants`，访问令牌携带授权标识，受保护请求从数据库核对授权状态；当前用户可通过 `GET /api/mcp/authorizations` 查看客户端并通过 `POST /api/mcp/authorizations/{client_id}/revoke` 撤销。刷新令牌使用行锁轮换，重放会撤销对应授权。数据库错误时拒绝访问。
- `scripts/upgrade_mcp_oauth_security.py` 只接受显式配置的本机 `gaitlogic_test_*` MySQL，支持重复执行；**尚未在隔离 MySQL 执行，不能用于生产迁移**。新结构已加入 `sql/schema.sql`；旧令牌与旧授权码需重新授权。
- 上述安全机制尚缺真实 MySQL 并发兑换、资源不一致、双用户完整 OAuth HTTP E2E、重启持久化及撤销隔离验收。代码和模型尚未经过完整审计，不应上线。

- 本机 MySQL 8.0.46 `127.0.0.1:3307` 已新建独立 `gaitlogic_test_mcp`，测试使用本机 root 凭据，并非权限受限的专用账号；生产数据库未用于本轮迁移。迁移脚本执行两次均成功，但当前测试库的基础表已由新版 ORM 创建，因此尚未证明旧表升级正确。
- 隔离 MySQL 协议级集成：两名合成用户各自注册客户端、登录授权、PKCE 换取令牌并调用 tools/list；刷新重放使用户 A 的访问令牌失效而用户 B 仍可访问，用户 A 无法撤销用户 B 客户端授权。此测试通过 FastAPI TestClient，未通过独立网络客户端，未读取真实训练数据，未覆盖并发或重启。
- 配置该隔离 MySQL 后，MCP HTTP、OAuth、MySQL 安全、Server、Knowledge 和训练集成测试合计 **51 passed**。其中 MySQL OAuth 安全集成是 1 个测试，覆盖多个步骤；这不是完整双用户训练工具 E2E。

近期训练通过已有 WorkoutLog 标识增加 `record_ref=workout_log:<id>`，来源仍由 `source` 区分；引用仅供追溯，不能作为授权。合成服务测试覆盖不同用户引用及重复查询稳定性，但尚未完成真实 MCP 与训练页面逐条核验。未新增数据库表或执行生产迁移。

Resource Binding：BLOCKED。Token 撤销：BLOCKED。稳定记录引用：已实现，完整真实一致性 BLOCKED。独立 MySQL 与双用户 OAuth E2E：BLOCKED。当前 SDK 无状态请求的本地 tools/list 和 tools/call 已实际通过，但旧协议 initialize、ChatGPT 客户端兼容尚未验收。生产及 ChatGPT 均 NOT READY。部署准备见 [mcp-production-rollout.md](../deployment/mcp-production-rollout.md)。

v0.3 定向回归：`tests/test_mcp_server.py`、`test_mcp_http.py`、`test_mcp_oauth_routes.py`、`test_mcp_knowledge.py` 和 `test_agent_training_integration.py` 合计 **46 passed、1 skipped**；跳过项需要本机隔离 MySQL。现有工作树的 MCP 和文档修改尚未提交。7 天与 28 天的真实数据一致性、两个真实账号和生产服务器只读审计均未完成。

## 验收结果

| 项目 | 结果 | 依据 / 限制 |
| --- | --- | --- |
| OAuth Discovery | PASS（本地） | 独立客户端读取本机受保护资源与授权服务器元数据；自动化测试覆盖 401 challenge。 |
| PKCE 登录 | PASS（本地真实授权） | 用户在本机浏览器完成 GaitLogic 登录和授权。 |
| Token Exchange | PASS（本地真实授权） | 独立客户端用授权码及 S256 verifier 换取令牌。 |
| MCP Initialize | BLOCKED | 此独立探针使用当前 SDK 的无会话协议请求，未单独验证 initialize；不能推断 ChatGPT 兼容。 |
| tools/list | PASS（本地真实授权） | 独立客户端发现 `get_recent_training`。 |
| 最近 7 天训练 | BLOCKED | 未完成真实独立客户端调用及对照。 |
| 最近 28 天训练 | PASS（本地真实授权，初步） | 先前真实调用成功，服务端当时返回 17 条并标记列表完整；未逐条对照页面或服务。 |
| GaitLogic 页面一致性 | BLOCKED | 未进行同时间点逐条核验；MCP 列表目前未暴露稳定活动 ID。 |
| 超范围参数 | PASS（合成测试） | 自动化测试覆盖超过 28 天、非法身份参数等；未完成独立客户端全部异常输入。 |
| 数据截断处理 | PASS（合成测试） | 截断和明细与汇总数量矛盾时标记不完整，保留原服务汇总及事实问题。 |
| 双用户隔离 | BLOCKED（真实双账号） | 现有合成测试覆盖服务端注入身份与禁止传入 user_id；未完成两个真实账号的 OAuth 并发测试。 |
| MySQL 集成测试 | BLOCKED | 未配置独立本机 `gaitlogic_test_*` 测试库；Docker 命令不可用。 |
| 公网 HTTPS | BLOCKED | 本机及沙箱外复核建议域名 `back.reol2020.cn` 时，TLS 证书主机名校验失败；该域名是否为实际生产 MCP 域名尚未确认。 |
| ChatGPT 连接 | BLOCKED | 未部署并验收公网 MCP，未检查当前账号的添加权限或完成授权。 |

本地真实调用使用此前经用户授权的数据库和账号；本轮未继续写入生产数据库。OAuth 注册测试曾在先前运行时可能向线上增加测试客户端记录，尚未进行任何清理。

## 数据与权限边界

- MCP `get_recent_training` 复用已有 Training Service，查询上限为 28 天、明细上限 20 条。服务端会按授权用户查询 WorkoutLog，并按已有规则处理关联计划及待处理设备活动。
- `details_complete` 表示列表与汇总的条数检查及上限状态；它**不证明** Garmin 同步完整，也不证明每条活动的所有字段完整。`data_quality`、`missing_reasons` 和 `fact_issues` 分别提供可用的缺口和一致性信息。
- MCP 不返回自由文本训练复盘或 GPS 轨迹。近期训练仍包含平均心率、RPE 等既有字段，属于用户授权给客户端的数据；`get_runner_state` 的动态 metrics 和 evidence 当前不返回，但 warnings、limitations 及状态仍需逐字段隐私审计。
- 仅有 `mcp:read`；访问令牌验证签名、目的、签发者、受众、有效期及 scope。只读工具不接受 `user_id`，且没有计划写入工具。错误 audience、过期 token、无 scope 和用户隔离有合成测试覆盖。
- **生产阻塞**：当前 JWT access token 没有即时撤销机制；OAuth refresh token 在轮换时标记撤销，但未见可供用户撤销授权的完整流程。JWT 的 `iss`/`aud` 是项目内部配置值，尚未证明与 OAuth issuer/resource 绑定满足外部客户端及生产威胁模型。OAuth `resource` 参数未形成完整绑定验证。登录授权、注册、token 路由的防暴力尝试/限流和日志脱敏需生产级审计。不要据此开放公网。

## 性能与稳定性

本轮 MCP 相关自动化：40 passed、1 skipped。它们是合成或进程内测试，不等同于真实 MySQL、双用户或公网压力测试。未执行隔离环境 20 次串行、10 次并发、数据库故障和重启恢复验收；成功率、p50/p95 和错误分布无可报告样本。

## 部署兼容与操作边界

本机基线为 `86831ad` 及本轮未部署修改；服务器实际 Git 提交、Nginx 配置、线上数据库迁移状态和已安装依赖未取得，不能仅凭“约 v0.16.1”推断差异，也不能确认可将补丁独立安全上线。仓库 `sql/schema.sql` 包含三个 OAuth 表定义，但不代表目标环境结构已核对完整。

生产前需要只读核对部署提交、依赖、三张 OAuth 表及已有迁移，审查当前 Nginx `/mcp`、`/oauth/`、`/.well-known/` 路由和 HTTPS 证书。配置示例应在不覆盖现有 `/api` 的前提下透传 Host、Authorization，设置受信任的反向代理来源、合适超时及流式缓冲；确切配置须根据实际站点配置编写和 `nginx -t` 验证。

上线方案需先准备经验证的代码及数据库备份、版本与环境变量清单、回滚命令、原有 Web/API 和未授权请求 smoke test；目前均未完成实际服务器核对，不执行生产修改。

## ChatGPT 参考

OpenAI 官方文档说明自定义 MCP 可通过 ChatGPT 网页端添加，支持 Streamable HTTP、OAuth，并受工作区权限和安全设置约束；OAuth 可使用 DCR，实际回调地址需以连接配置为准。当前项目 DCR 与目标客户端是否互通仍待实测。[OpenAI 自定义 MCP 文档](https://developers.openai.com/api/docs/guides/custom-mcp-server)；[OpenAI OAuth 文档](https://developers.openai.com/plugins/build/auth)。

## 最终判断

- Remote MCP 技术验收：**BLOCKED**。已有一次本地真实授权与 28 天读取成功，完整一致性、双用户及 MySQL 验收未完成。
- 生产部署验收：**BLOCKED**。TLS 名称异常、生产版本/Nginx 未核对，且令牌撤销与权限安全门槛尚未满足。
- ChatGPT 网页端验收：**BLOCKED**。尚无经过验收的公网端点，也未确认账号权限。
