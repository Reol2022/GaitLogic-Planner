# 独立管理控制台 MVP

## 基线与范围

2026-11-06，分支 `codex/admin-console-mvp`，HEAD 基于 `066f1dc`。创建分支时上一轮 Core Experience/MCP 修改仍未提交，全部保留；本轮没有提交、合并、推送、部署或修改生产数据库。

审计发现已有 `/api/admin`、`require_admin_user`、`admin_ai_settings` 和跑者端管理页面。课表生成按请求读取数据库配置；Coach、周复盘和 Plan Design 使用环境配置解析的 Model Profiles。两者不是一个可随意替换的全局模型开关。

## 架构

```text
跑者入口 index.html       管理入口 admin.html
训练 / 日历 / Coach       独立登录 / 概览 / 用户 / AI / 审计
          \                 /
             FastAPI / MySQL
          /api/admin/console/*
               管理员权限校验
```

默认统一打包到web-dist，管理端也可以按需单独打包到admin-dist。

管理前端保留独立 HTML、Vue 根组件、路由、CSS 和 HTTP client，不加载跑者 AppLayout，但共用一个开发服务。默认入口 `/admin.html#/`，跑者入口为 `/`。`npm run build` 同时打包两个入口；仍可单独构建后台。这不是独立微服务。

## 已实现

- 运行概览：账号总数、有效账号数、累计同步任务状态。没有数据不显示为零；不是 AI 成功率或系统健康评分。
- 用户管理：搜索、分页、修改角色/停用状态、确认操作、并发冲突检查、禁止停用或降权当前管理员。不提供删除、冒用用户或阅读训练/聊天功能。
- AI：课表模型 ID、超时、每日额度、冷却、采样和输出预算。保存草稿不生效，发布需显式确认；发布前保留恢复快照。历史恢复生成新草稿，仍需发布。
- Coach 档位：读取当前配置的模型、Thinking 和超时，不在线修改。不能将环境配置存在误称为真实模型已可用。
- 审计：管理员 ID、动作、对象 ID、字段名、UTC 时间，不保存变更值或密钥。新控制台写入与审计同事务；原有用户、AI 设置写入也记录带 `LEGACY_` 前缀的审计。不是覆盖所有既有系统设置/科学规则操作的统一审计。

## 一致性与权限

所有控制台路由服务端依赖 `require_admin_user`，每次从数据库核对账号，不接受前端角色作为授权依据。用户端和后台端使用不同存储键；后台令牌只在本标签页的 sessionStorage 保存，退出清除，不借用跑者 localStorage 令牌。两个入口仍使用现有账号/JWT机制，不宣称新增独立身份系统或防XSS能力。

课表生效配置仍使用 `admin_ai_settings`，增加 `config_version`。草稿指纹绑定配置、Provider 地址和递增版本号，防止旧草稿以及“改动后恢复相同值”的旧页面覆盖新版本。发布通过 singleton 行锁串行化；同一草稿只发布一次。新增历史表不保存 Key，发布不修改原 Key、URL，也不会把环境密钥复制进版本表。

各Worker的新请求按现有机制查询数据库，无进程内发布缓存；已经获取配置的进行中请求不追溯改变。模型结果和真正的任务成功还须经过原有验证链。

用户权限变更也通过配置 singleton 串行化，并重新核对操作者角色，避免互相停用后仍沿用旧身份。本版只有现有 admin/user 两种角色，尚未引入运营/超级管理员等RBAC。

## 数据结构与迁移

- `admin_ai_settings.config_version`：INT，默认0。
- `admin_config_revisions`：操作者外键、DRAFT/PUBLISHED/SNAPSHOT、非密钥配置JSON、基础指纹、时间。
- `admin_audit_events`：操作者外键、动作、对象、变更字段名、时间。
- `sql/schema.sql`、ORM、初始化脚本同步更新。

新增脚本：`scripts/upgrade_admin_console.py`。只增加上述结构，不改训练业务表。默认只允许本机 `gaitlogic_test_*`，明确提供连接URL和目标库名，禁止从普通MYSQL配置猜生产目标。

```powershell
# 先在私有环境安全设置 GAITLOGIC_ADMIN_MIGRATION_DATABASE_URL，不要把密码发到报告或Git
python -m scripts.upgrade_admin_console --database gaitlogic_test_admin_example
```

生产迁移需另外审查并授权 `--allow-non-test`，同时精确匹配 `--database`。本轮没有执行。MySQL DDL不是整体事务：保留备份，单列ALTER和两张CREATE可重复执行；失败先核对元数据，再按相同步骤重试，不通过DROP表清理。

升级代码前先迁移：旧设置服务现在也需要版本字段与审计表。回滚应用时可保留新增表/字段，不删除审计或恢复训练数据库。发布过的课表参数可通过恢复草稿回退，不能仅靠重启撤销数据库配置。

## 本地运行

```powershell
cd E:\我的项目\Gaitlogic-planner\web
npm run dev
# 跑者 http://127.0.0.1:5173/
# 后台 http://127.0.0.1:5173/admin.html#/login
# admin:dev 为同一服务的兼容别名，不需要再启动第二个服务
# 后端使用原有启动方式，默认代理到127.0.0.1:8000

npm run typecheck
npm run test
npm run build
# web-dist 同时包含index.html和admin.html
# 可选 npm run admin:build：单独输出admin-dist，基础路径仍为/control/
```

普通用户不能进入；后台不提供自助注册或自动升管理员。已有管理员可用，首次管理员创建需沿用经过授权的既有运维流程，不硬编码初始密码。日常本地库尚未自动执行新迁移，因此直接打开新页面前需要先完成迁移并重启使用本分支的后端。

## 部署边界

推荐以后使用独立管理子域名，构建时将 `ADMIN_PUBLIC_BASE=/`，站点根目录指向对应的 admin-dist，首页为 admin.html，`/api/` 反向代理同一FastAPI。使用Hash路由，不需要后端增加SPA路由。实际域名、证书、Nginx路径需在获授权部署时核实，本文不覆盖现有站点。

同站点也可部署统一web-dist，后台访问 `/admin.html#/login`。开发与preview服务兼容旧 `/control/login`、`/control/` 等已知路径，重定向到管理入口；生产Nginx需另加兼容重定向，Vite中间件不会随静态产物运行。跑者侧仅管理员显示“管理控制台”链接，登录状态仍相互独立。

首次打包后必须重新核对资源URL、TLS、反代、服务端权限、数据库版本、备份和管理入口的网络访问控制。可以再叠加IP白名单或VPN，不可将前端隐藏当成鉴权。

## 真实验收与限制

测试使用 `127.0.0.1:3307` 的 `gaitlogic_test_admin_*` 隔离库和合成用户；不查询生产数据。覆盖路由权限、精度/字段约束、并发发布、旧指纹拒绝、恢复草稿、密钥保持、用户状态CAS、自我保护、分页、同事务审计、历史Schema重复/部分升级恢复、真实HTTP登录与发布。

浏览器脚本 `tools/admin_console_smoke.cjs` 使用合成API，验证桌面/手机登录与四页、取消发布不发送POST、无页面水平溢出和无JS运行错误。不是浏览器连接真实模型或真实生产账号的端到端验收。

未完成：在线更换Provider/Key、付费连接测试、Coach档位在线发布、同步任务管理写操作、AI成功率/费用统计、多角色RBAC、双因素认证、生产部署。本版不应被称为完整生产运维平台。

### 本轮执行结果

| 检查 | 实际结果 |
| --- | --- |
| 控制台权限、Schema、真实MySQL迁移与发布、API结构 | 22 passed，0 skipped |
| 包含控制台权限的 MCP / Required Facts / 同步重试定向回归 | 55 passed，0 skipped（与上一组有重叠，不相加为总覆盖数） |
| 前端 Vitest | 150 passed / 28 files |
| Typecheck | PASS |
| 管理前端独立构建 | PASS，存在大于500KB的bundle警告 |
| 桌面与移动浏览器 | 各登录及4页面通过；取消发布未发起写请求 |
| git diff --check | PASS |

没有执行完整全仓pytest，不宣称真实LLM质量通过。浏览器截图及构建产物在仓库外私有目录。既有前端周复盘测试仍有未注册el-tag的Vue警告，不属于新增控制台错误。

### 后续授权数据库迁移（2026-11-06）

上述“未迁移日常/生产库”描述对应初次开发交付。用户随后明确授权将后台结构同步至当前配置指向的线上数据库，已完成：

- 只读核实MySQL 8.0.45，确认缺少config_version及两张管理表，既有设置singleton存在。
- 使用 `tools/admin_console_db_upgrade.py`，显式核对目标主机、端口与库名；迁移前备份受影响表的DDL与既有记录。
- 备份保存在仓库外私有目录，经Windows DPAPI加密并回读解密验证；原始配置与密钥未进入源码、日志或本文。该备份依赖原Windows用户密钥，非可公开分发的SQL文件，也不是全业务数据库备份。
- 增加版本字段、配置历史表、审计表；迁移前后既有AI配置记录保持一致。ORM读取成功；不迁移或覆盖任何训练记录。
- 未发布配置草稿，未调用模型，未上传代码、重启线上服务或部署新版本。真实浏览器登录与端到端业务仍由用户刷新后验收。

迁移工具仅允许显式目标与显式 `--apply`，拒绝把备份写进仓库；发生异常时不输出可能包含凭据的原始SQL异常，也不自动执行破坏性恢复。恢复前需在私有环境使用原Windows账号解密核对备份，不能通过删表或覆盖现有业务库处理。
