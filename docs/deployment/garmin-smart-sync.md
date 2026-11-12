# Garmin Smart Sync v1.0

部署前状态（2026-11-12）：本地候选已实现，真实 Garmin 端到端结果与生产发布须另行核验，不能以合成测试替代。

## 首次生产发布结果（2026-11-12）

- 代码提交 `a82d94f` 已合并 master 并推送两个远程仓库；数据库完整私有备份与环境文件备份保存在服务器受限部署目录，未上传 Git。
- 生产加法迁移重复运行通过，保留旧表数据；current 已切换新发布目录，原发布保留用于回切。
- 后端健康、主前端、管理前端、RAG 就绪检查通过；MCP 未授权请求仍拒绝，公开版本为 `0.16.8-facts-v3.3-smart-sync`。
- 独立 Worker 为 active，核查时重启次数为 0。首轮 scheduled / activities 任务成功并提交，失败数为 0；未开启任何用户此前关闭的自动同步或自动恢复偏好。
- 授权 MCP 训练查询连续两次返回 SUCCEEDED、新版本和 freshness，当前连接所属用户关闭自动同步时正确返回 AUTO_SYNC_DISABLED。切换后曾有一次外部宿主临时调用失败，随后重试及再次核验通过，不将首次失败记为成功。
- 以上不等于真实恢复同步、所有登录场景或移动端浏览器全部完成端到端验收；这些场景仍以合成集成/组件测试为主要证据。

## 审计与复用边界

- 基线 `74db603`；当前分支 `codex/garmin-smart-sync-v1`。该分支保留上一轮尚未提交的训练事实可靠性修改，不将它们描述成已经发布的依赖。
- 现有 Garmin China Provider 使用 garminconnect/garth 中国区会话及加密 Token 存储，活动分页、详情、laps 和每日恢复事实已有实现。本轮不增加 Provider，也不改变账户区域。
- 原有 `ExternalSyncJob` 已持久化排队状态、认领次数和结果；`ActivitySyncPipeline` 在提交后更新 Runner State。本轮继续使用它们，不增加第二套任务/事实写入管线。
- 既有 `auto_sync_enabled` 原先只保存偏好，没有调度执行。原有任务认领仅约束一个 job，不提供连接级互斥；本轮补充连接级 Lease。
- 上线前只读核查：生产基线 `74db603`，Gunicorn 当前为 1 个 Worker，MySQL 8.0.45、FastAPI 0.136.3、MCP SDK 2.0.0；Smart Sync 表尚不存在。数据库备份工具可用，环境文件保持既有服务组可读权限。已有自动同步偏好保留，不批量开启其他用户。

## 三种触发链路

```text
独立 Worker 定时检查 ─┐
登录 / 已登录首页 ────┼─> Coordinator ─> ExternalSyncJob
OAuth 验证后的 MCP ───┘        │                 │
                          新鲜度 / 退避        独立 Worker
                                                │
                                       ActivitySyncPipeline
                                                │
                                       Garmin Sync Service
                                                │
                                       现有 Garmin Provider
                                                │
                                       MySQL / Runner State
```

- 全局 `GARMIN_SMART_SYNC_ENABLED=false` 默认关闭；用户需在 Garmin 页面主动开启自动同步。恢复自动同步是单独的默认关闭选项。
- 定时默认 30 分钟（可配置 30～1440 分钟），独立进程每 30 秒扫描一次到期连接及排队任务。初始和后续检查带连接稳定错峰；登录/首页/MCP 以 15 分钟新鲜度和 5 分钟最近尝试冷却控制提交。
- 普通增量回查最近 3 天，每日一次扩大至 7 天；自动恢复只检查当前本地自然日及前一天。参数是本地保守策略，不是 Garmin 官方接口额度承诺。
- 自动详情补全每任务最多 3 个活动，保留原有手动入口。它不是全量历史详情补齐保证；近期活动很多时，仍需专门的受控补偿机制。
- 登录只执行独立数据库事务，不请求 Garmin。首页提示轮询真实任务状态，最多 60 次，页面离开停止轮询；完成后通知“今日”页面重新获取训练相关区域，后台任务不依赖页面存活。
- Worker 每轮最多扫描 1000 个启用连接、处理 20 个排队任务；v1 面向小规模自用/内测，未进行容量或生产压力验收。

## 并发、故障与数据保护

- 提交时锁定当前连接行，共享原手动同步任务表；已有 queued/running 任务直接复用，跨触发源不追加重复任务。
- `garmin_smart_sync_state` 保存连接级 180 秒 Lease、随机 token 和当前任务 ID，每 30 秒续租。任务提交前锁定并验证当前 token；租约丢失或无法验证时回滚业务写入。失败结果也受相同 token 保护。
- Worker 启动/扫描时回收过期 Lease，将原运行任务标记失败，并退避后重新允许同步；旧 Worker 无法靠迟到 Provider 结果重新取得写入权。
- 执行前重新检查用户状态、连接状态、自动同步及恢复选项。取消自动恢复后，全范围自动任务收窄为活动同步，恢复专属任务取消；既有手动同步仍是明确的用户操作。
- 错误按 AUTH、RATE_LIMIT、NETWORK、PARSING、DATABASE、PROVIDER 分类，指数退避封顶 6 小时，限流至少等待 30 分钟。认证失效要求重新连接，不无限重试。
- 当前 SDK 主要提供安全错误码，未统一暴露可信 `Retry-After`；因此本版本使用保守退避，不能宣称已精确遵循所有上游动态等待时间。
- 可选登录/MCP 检查将 MySQL 行锁等待临时限制为 1 秒，并在返回连接池前恢复。检查失败返回 `CHECK_UNAVAILABLE`，不影响已认证登录或已读取事实。
- 沿用 ExternalActivity 去重、WorkoutLog 关联、RPE/备注来源优先级，不新增正式计划写入。原始设备数据、Token 和真实健康信息不进入公开测试、文档或 Metrics。

## MCP 契约

工具名称、参数及主要事实数据结构不变。`get_recent_training`、`get_training_detail`、`get_runner_state`、`get_recovery_trend` 在成功读取后检查并申请后台更新，使用独立事务，不等待 Garmin。

新增可选顶层 `freshness`：包含范围、成功抓取时间、各数据范围时间、当前状态、job_id、退避、错误类别及本次事实读取开始时间。成功抓取时间不是上游数据完整性证明；若同步晚于本次读取才完成，返回 `REFRESHED_AFTER_READ`，要求重新查询，不将旧快照声称为新数据。

- 普通训练工具仅申请 `activities`，不能间接同步恢复指标。
- 恢复工具在打开数据库前校验 `mcp:recovery:read`；用户还须单独开启自动恢复同步。14/28 天查询适用相同权限，输入范围不影响授权。
- 知识检索与纯本地今日计划不触发同步。
- 四个设备依赖工具改为 `readOnlyHint=false`、`destructiveHint=false`、`openWorldHint=true`，说明可能更新外部事实缓存，但不允许正式计划或人工输入写入。客户端可能需要刷新工具定义、重新确认调用；这与 OAuth 重新授权不是同一个步骤。

设计依据：[MCP 工具注解说明](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)、[MySQL 8.0 锁定读取与 SKIP LOCKED](https://dev.mysql.com/doc/refman/8.0/en/select.html)。注解不是鉴权，权限仍由服务端强制校验。

## 数据库迁移

增量新增 `garmin_smart_sync_state` 表及 `external_sync_job.data_scope`、`trigger_source` 两列；旧任务默认 all/manual，保留旧语义。ORM、初始化入口及 `sql/schema.sql` 同步更新。无需 Redis/Celery 或 Alembic。

```powershell
# 在已检查数据库目标的发布环境，先备份，再执行；本轮未执行生产操作。
python -m scripts.upgrade_garmin_smart_sync --apply
```

迁移仅增加结构，可重复执行，也可从部分新增列已完成的状态继续。MySQL DDL 不是整批原子事务；出现失败时停止启用功能，检查元数据后修正权限/连接问题，再运行同一脚本。不自动删除列、重建业务表或清空任务。

## 启动与部署顺序

1. 审查整个候选分支与上一轮事实层依赖，先完成本地验收和发布批准，再合并、推送和上传；未经授权不执行后续生产步骤。
2. 在维护窗口确认当前代码、MySQL 目标、可恢复备份、Python 环境及服务账户；按现有发布方式上传候选，不猜测生产目录或进程名。
3. 关闭全局 Smart Sync，执行上述加法迁移，检查表/索引/两列；不自动更改用户开启状态。
4. 更新 API/前端代码和依赖，验证旧手动同步、登录及 MCP；迁移先于新版代码读取新任务列。数据库不用迁回旧结构即可兼容旧程序。
5. 配置 `GARMIN_SMART_SYNC_ENABLED=true`，以与 API 相同的环境和服务账号启动一个独立 Worker：

```powershell
python -m scripts.garmin_smart_sync_worker
# 或由外部调度器定时执行一次；不要与常驻进程重复配置。
python -m scripts.garmin_smart_sync_worker --once
```

6. 用一个授权测试账号开启自动同步，观察 queued → running → succeeded、分范围时间及 Runner State；低频验证后逐步开放。真实 Garmin 验收须单独授权，不能以 Mock 结果代替。
7. Worker 使用 systemd/Supervisor/宝塔独立进程管理，不在每个 Gunicorn/FastAPI Worker 内启动。Linux 模板见 [service 示例](../../deploy/garmin-smart-sync.service.example)，其中路径与账户必须替换为已核实值。Windows 可由独立终端或任务计划程序运行相同 Python 模块。

### 健康与回滚

- 检查 Worker 存活、排队任务年龄、租约更新时间、错误分类及分范围成功时间；不以接口 HTTP 200 代替同步完成。
- 回滚先禁用新请求并停止独立 Worker，再等待或取消受控的在途任务；切回已有稳定 API/前端并恢复原手动同步。保留新增表和列，不执行破坏性逆向 DDL。
- 若需恢复备份，先阻断所有同步写入并单独审查备份恢复影响；不自动覆盖业务数据库。
- 首轮真实活动同步与生产 Worker 已验证；恢复自动同步及桌面/移动端浏览器的完整真实验收仍待补充，不以已发布代替所有使用场景通过。

## 开源边界

协调器、调度器、Lease、迁移、通用 UI、合成测试和本说明可开源。真实用户数据、Garmin 凭据、OAuth Token、生产配置、日志和备份必须私有。自动同步不能被当作新增外部账户访问授权。

## 本地验收（2026-11-12）

| 分组 | 实际结果 |
| --- | --- |
| Garmin、Auth、MCP/OAuth、Coach、Runner State、Weekly Review、AI Plan 等相关回归 | 602 passed、1 skipped，211.96 秒；跳过的恢复迁移随后在独立空库补跑 |
| Smart Sync / 网络错误分类 / MCP 发现及兼容契约最终定向组 | 54 passed、0 skipped，22.11 秒；与主组有重叠，不重复累加 |
| 独立空库 Garmin Recovery 迁移 | 1 passed、0 skipped，7.84 秒 |
| 独立空库历史 OAuth 迁移 | 1 passed、0 skipped，12.90 秒 |
| Coach Chat MySQL | 11 passed、0 skipped，78.11 秒 |
| AI Plan 个性化 MySQL | 16 passed、0 skipped，76.31 秒 |
| 前端 | Typecheck、42 文件 222 项 Vitest、生产构建通过；新增组件组单独验证 6 项通过 |
| 静态检查 | `git diff --check`、52 个候选文件的凭据模式检查通过，受保护无关脚本 SHA256 保持不变 |

Python 使用 `-B -m pytest -p no:cacheprovider -q`，全部数据库测试限定本机 `127.0.0.1:3307/gaitlogic_test_*` 合成库。迁移独立运行，不在有业务数据的开发库模拟删除/中断。一次旧 MCP 注解断言失败已按新的缓存副作用契约修正，后续定向重跑通过；没有关闭 OAuth、跳过安全测试或放宽事实规则。

最终增加的 Worker 正常中断恢复用例与 Smart Sync MySQL 全组再次运行：31 passed、0 skipped，10.32 秒，包含权限撤回、迟到回写、心跳与迁移幂等。

前端测试存在既有 Element Plus 测试桩警告，构建存在包体积警告；不属于业务测试失败。没有将未执行的真实 Garmin 或浏览器验收写成通过。
