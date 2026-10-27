# Garmin Recovery Sync 审计与修复（v0.16.6）

## 审计基线

- 开发基线：`master` / `28b01da`。
- Coach Chat v1.2 独立工作树仍停留在 `5e1f5c7`，落后于 master，不作为本轮实现基线。
- v0.16.1 历史工作树为 `b88b0be`；master 已包含其恢复数据 Provider 代码及后续 Garmin 修复。
- 审计时本机没有运行中的后端监听端口，因此无法把某个运行进程确认到具体 commit。

## 现有链路实际状态

链路为：

`garminconnect private API -> GarminActivityProvider -> Garmin sync job -> ProviderRecoverySnapshot -> DailyRecoveryCheckin -> Runner State / Today Readiness -> Coach Tool`

Provider 已真实调用睡眠、每日心率、HRV、全天压力、Body Battery 和呼吸率接口。现有方式是非官方 `garminconnect` 客户端及区域绑定的 garth 会话，不是 Garmin Personal API。

审计发现以下缺口：

1. 恢复同步日期由活动日期集合产生。休息日或没有新活动时不会请求恢复数据。
2. Provider 已归一化压力、Body Battery、睡眠评分和呼吸率，但数据库只保存睡眠时长、静息心率和 HRV。
3. 任意一次手工恢复打卡都会把整条记录标记为 manual，导致后续 Garmin 客观指标无法更新。
4. Runner State 不读取 `DailyRecoveryCheckin`，Coach 的 `get_runner_state` 虽声明提供 recovery domain，实际没有恢复事实。
5. 恢复端点网络失败、权限拒绝、设备无数据经常被统一压缩为 unavailable，无法与正常缺失区分。
6. 恢复数据变化未计入 Runner State material change，恢复-only 同步不会触发后续快照更新。

## 本轮修复

- 恢复同步改为独立的日历窗口；无活动和休息日仍执行，最多回填 31 个自然日。
- 扩展现有 `daily_recovery_checkin`，保存睡眠评分、压力、Body Battery、呼吸率、Pulse Ox、逐字段来源、同步时间、缺失字段和安全 limitation。
- 在连接表保存恢复同步的最近尝试、最近成功和安全错误码；失败不覆盖旧的有效事实。
- 手工优先级改为逐字段控制；填写主观疲劳、腿感或笔记不会阻止 Garmin 更新睡眠、静息心率和 HRV。
- Runner State 增加只读恢复事实与新鲜度，不修改既有疲劳评分或训练规则；Coach Tool 可以读取这些事实。
- 恢复事实发生实际变化时计入 material change；单纯刷新同步时间不制造变化。
- “负荷与恢复”页面增加紧凑设备恢复卡，显示睡眠、HRV、静息心率、Body Battery、同步时间和缺失/失败提示。

## Garmin Personal API 可行性

官方 Developer Program 说明 Personal API 面向个人、pull-only 的 Activity/Health JSON 访问：

- https://developer.garmin.com/gc-developer-program/overview/
- https://developer.garmin.com/gc-developer-program/personal/swagger-docs/
- https://developer.garmin.com/gc-developer-program/personal/personal-faq/
- https://github.com/garmin/connect-personal-api-python

Swagger 与官方 Python SDK 覆盖 Sleep、HRV、Stress、Body Battery、Daily Summary 和 Heart Rate，功能上可以替代本项目当前私有端点调用。但本轮未接入，原因是：

1. 官方 SDK 当前要求 Python 3.12+，项目运行基线为 Python 3.11。
2. 本地没有配置 Personal API Key，无法完成真实账户协议和区域验收。
3. Personal API 仅允许个人使用，不能直接推导为未来多用户商业授权方案。

结论：修复后的现有 Provider 暂时保留；未来应在升级 Python 基线并获得个人 Key 后，将官方 Personal API 作为独立 Provider 做真实 smoke test，而不是在当前 Provider 内自动跨区域重试。

## 数据语义

- Garmin 没返回的指标保持 `NULL`，绝不写为 0。
- `device_data_status` 区分完整与部分数据；连接级错误区分同步失败。
- 昨晚恢复数据允许以昨天日期作为当前有效事实；超过一天标记 stale。
- 手工 RPE 和训练笔记不在恢复同步写入范围内。
- Body Battery 仅作为一个设备事实，不直接代表“恢复充分”。
- 缺少 HRV 只形成局部数据缺口，不阻断全部训练分析。

## 部署顺序

1. 备份目标 MySQL 数据库。
2. 运行 `python scripts/upgrade_v0166_garmin_recovery.py`（可重复执行）。
3. 部署后端代码并重启进程。
4. 部署前端构建产物。
5. 使用授权测试账号执行一次 Garmin 同步，核对连接状态、恢复卡、Runner State 和 Coach 事实。

本轮没有执行生产迁移、真实 Garmin 请求、部署或远程 Git 操作。
