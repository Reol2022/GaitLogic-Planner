# Mobile REST 与 MCP 路由隔离修复

## 根因与证据

- 修复前，线上 OpenAPI 不包含三个 Mobile REST GET。对 `/api/mobile/training` 的请求返回 401，并带 MCP `resource_metadata` 挑战。
- `server/main.py` 最后在根路径挂载 MCP 子应用。原 MCP HTTP 安全中间件没有先限制请求路径，因此未知 REST URL 也先进入 MCP Token 验证。
- Mobile 客户端将该 401 视为普通 Web 登录失效，清除身份并跳回登录；日志中的页面切换超时与这一过程相关，但不据此声称所有导航超时都已解决。

## 最小修复与实际发布

2026-11-25 经授权完成五文件后端补丁发布：

- `server/main.py`：注册 Mobile 路由。
- `server/api/routes/mobile.py`、`server/schemas/mobile.py`、`server/services/mobile_read_service.py`：三个普通 JWT、用户隔离、只读本地事实的 GET，不通过 MCP HTTP。
- `server/mcp/http.py`：只有精确 `/mcp`、`/mcp/` 进入 MCP 身份验证；未知路径返回 404，无 OAuth 挑战，不查询 MCP 身份数据库。

保留既有 SDK 生命周期、Resource Binding、Scope、撤销和权限边界。不新增工具，不修改 Garmin Provider，不触发同步、不调用模型、不修改数据库结构、环境配置或 Nginx。

生产基线仍是 `3e4a00a`，叠加补丁标识 `mobile-rest-routing-20261125`，不是一次完整 Git 版本切换。补丁包 SHA256：`dad5b9cd7506cd62fbd1c6cdf4268ed40bfdcf8d0964a4be57d486f992e60ede`。仅从干净基线加入这五个文件，未发布当前工作区的 Session、配速计算器或其他未提交内容。未合并、提交或推送 Git。

发布前逐文件原始哈希匹配并备份，按实际服务用户验证导入，平滑重载 Gunicorn。第一次前置检查因脚本额外转换行尾而误拒绝，尚未写入生产代码；确认原始字节与基线一致后改为严格原始哈希检查再执行。最终私有部署回执 PASS，备份保留；无需数据库回滚。

## 客户端改动

Mobile API Client 遇到 REST 请求上的 OAuth `resource_metadata` 挑战时报告接口协议错配，不删除 Web 登录态、不自动重试或触发冲突跳转；普通 Web 401 仍按原规则使身份失效。今日页显示安全的实际错误类别，不把该错误统一归为网络不可用。

客户端为本地工程改动，微信小程序与 Android Vapor 开发编译通过；没有上传或发布小程序/App。

## 验证结果

| 项目 | 结果 |
| --- | --- |
| 干净基线 HTTP/MCP/Mobile 单元与契约组 | 60 passed、0 failed、0 skipped |
| 干净基线隔离 MySQL/Mobile/Facts 组 | 33 passed、0 failed、0 skipped |
| 干净基线隔离 MySQL OAuth/Server 补充回归 | 19 passed、0 failed、0 skipped；无数据库初跑为 18 passed/1 skipped，配置隔离库后补齐 |
| Mobile 静态检查和单元测试 | PASS；32 passed、0 failed、0 skipped |
| 微信小程序与 Android Vapor 开发编译 | PASS；不是发行或真机验收 |
| 公网 OpenAPI | 200，三个 Mobile 路径已注册 |
| 公网与微信模拟器无 Token Mobile 请求 | 401，普通 REST 拒绝，无 MCP OAuth 挑战 |
| 公网未知 Mobile 路径 | 404，无 OAuth 挑战 |
| 公网后端健康 | 200 |
| 既有公网 MCP 与 OAuth 元数据入口 | 未授权 MCP 401；元数据 200 |
| 真实账号完整登录和训练展示 | 待用户重新登录验收；没有读取密码或伪造认证 |

分组覆盖有重叠，不相加为独立用例数。首次干净环境 MySQL 组缺合成 JWT 测试配置，出现 5 failed/28 passed；补充仅用于测试的密钥后完整重跑为 33 passed，不涉及生产密钥。隔离 MySQL 使用 127.0.0.1:3307 的专用受限账号与 `gaitlogic_test_*` 数据库，结束后清理；不使用生产账号或训练数据。

## 回滚与边界

备份与发布脚本仅在私有部署目录保存。回滚时先核对当前运行目录和文件是否仍为本补丁版本，只恢复五个已备份文件；新文件保留在私有备份而不覆盖未知修改，再平滑重载。不得回退数据库、Nginx、密钥或其他后续补丁。

受保护的无关迁移脚本未更改。真实账号、Token、健康记录、生产环境和部署绝对路径不纳入本报告。
