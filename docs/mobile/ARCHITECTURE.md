# Mobile 架构与审计

## 选型核验

2026-11-25 核对的[官方正式版记录](https://doc.dcloud.net.cn/uni-app-x/release.html)为 `5.34.2026102909`。目标版本不是本机实际编译版本。manifest 明确开启 `uni-app-x.vapor` 和样式隔离 2，页面为 `.uvue` Composition API/TS；入口采用官方仍提供的 `main.uts`。最新项目与入口文档的版本叙述有差异，最终须以目标编译器产物确认。

[蒸汽模式说明](https://doc.dcloud.net.cn/uni-app-x/app-vapor.html)区分 App Vapor、Web 与小程序机制；Web 预览不是原生引擎验证。[状态管理文档](https://doc.dcloud.net.cn/uni-app-x/tutorial/store.html)提供 reactive 和 Pinia，本版使用小型 reactive 身份状态，不将未本机验证的 Pinia/uni-ui x 当作已兼容依赖。没有引入 Element Plus、浏览器 ECharts 或第三方原生 SDK。

## 分层

```text
.uvue 页面 / 原生 UI
       ↓
AuthSession / ChatService / API Client
       ↓
Transport / Storage / Platform
       ↓
uni.request → REST → FastAPI 原服务 → MySQL

外部 ChatGPT → MCP → 同一事实投影（独立授权边界）
```

页面负责展示，服务负责访问，身份集中管理。业务依赖 Transport/Storage 接口，不依赖浏览器 Axios/localStorage/DOM；不新增 Agent 或数据库，不重构 Monorepo。

## API

| 路径 | 用途 |
| --- | --- |
| POST `/api/auth/login`、GET `/api/auth/me` | 原账号与 Web JWT，不用 MCP Token，不新建 Refresh Token |
| GET `/api/planned-workouts?start_date&end_date` | 计划态，空计划不隐藏实际训练 |
| GET `/api/runner-state/current` | snapshot 下恢复和质量，LOW/NORMAL 不代表恢复许可 |
| GET `/api/integrations/garmin/status` | 训练与恢复的独立同步时间 |
| GET `/api/training-calendar?month` | 日历展示，不作完整训练量汇总 |
| `/api/coach/conversations`、messages、turn status | 原会话、幂等消息、进度与最终 JSON |
| 新 GET `/api/mobile/training` | 1–28 天、20 条/页、游标、完整窗口汇总与无计划日志 |
| 新 GET `/api/mobile/training/detail` | 稳定引用、多活动选择、分段与完整性 |
| 新 GET `/api/mobile/series` | 最大 31 天服务端日序列，实际日期优先，距离缺失 null |

新路由共用 DTO 与纯事实投影，认证仍为 get_current_user，不经 MCP HTTP/OAuth，不排队同步或写入业务，无 Schema 迁移。采集时间不是上游同步证明，响应 no-store。

旧 `build_daily_training_loads` 存在实际日期筛选、计划日期归桶的冲突，移动端不直接复用该分桶；原 Web 算法仍需独立修复。日历压缩同日记录，不能拿来汇总实际跑量。

## 身份与传输

请求捕获身份 epoch，退出/切换后拒绝迟到响应；401 清除身份回登录，网络失败不删除尚未证实失效的 Token；写请求不自动重试。API/Token 按构建环境隔离，地址改变需退出并重建栈。普通存储不是加密 Keychain，服务端全端撤销未实现。

现有 Coach 返回最终 JSON，进度 GET 不包含 token 文本；ChatTransport 使用真实 JSON + 有界轮询。取消客户端等待不代表服务端停止，未知结果保留 turn ID 核对。UTF-8/SSE 探针仅测试纯协议，不连接不存在的 SSE 路由。[uni.request 分块 API](https://doc.dcloud.net.cn/uni-app-x/api/request.html)仍须逐平台实测。
