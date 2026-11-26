# GaitLogic Mobile v0.1.0

状态：本地基础工程与隔离验证，**不是完整跨端验收或已发布版本**。

界面设计：[活动优先视觉方案](VISUAL_DESIGN.md)。当前功能分支提交范围为移动客户端及文档；本地端到端测试需要另配包含 Mobile REST 接口的后端。

2026-11-26：新增计划与执行原生工作区，当前 28 个页面；本地首批迁移不等于全面迁移完成或已发布。逐项范围与验证见 [Web 迁移清单](WEB_MIGRATION.md)。

2026-11-25 增量：三个 Mobile REST GET 与 MCP 路由隔离已获授权以五文件最小补丁部署生产；客户端未上传发行，真实账号登录和训练展示仍待复核。范围、证据及回滚见 [REST/MCP 路由修复](../evaluation/mobile-rest-routing-20261125.md)。

基线 `96f32d4`，分支 `feat/mobile-v0.1.0-foundation`。既有 Session、配速计算器等未提交修改保持不变，不纳入本轮移动端功能。Web 实际为 Vue 3 + Vite，目录为 `web/`，不是 Nuxt。

## 范围

- 独立 `mobile/`：uni-app x Vapor 标记、`main.uts`、TS `.uvue`、五个原生导航（今日 / 训练 / Gilo / 工具 / 我的）和登录/详情/设置。
- `uni.request`、五种 HTTP 方法、超时与取消、JWT、401/429、账号代际隔离；不记录凭据、正文或健康数据，不自动重试写请求。
- 原账号登录、启动身份恢复、仅 Token 持久化；没有新建 Refresh Token 或微信独立账号。
- 今日计划与实际训练分开、近期训练分页、多活动独立选择、服务端日序列图表与日历、Runner State 与 Garmin 只读展示。
- Gilo 为真实 **JSON_WITH_STATUS_POLLING** 回退；取消客户端等待不代表服务端任务停止，没有伪造逐字流。
- 新增三条 JWT 保护的 REST GET，共享原事实投影，不经过 MCP HTTP、不触发 Garmin 同步或计划修改，无表结构迁移。

## 验证边界

本机 HBuilderX 已升级并核验为 **5.34.2026102909**，微信开发者工具登记版本为 **2.02.2609250**。微信小程序与 Android Vapor 字节码目标均已通过实际开发模式编译，各包含 8 个页面。DCloud AppID 已配置，官方 Vapor 运行插件已安装。微信服务端口配置生效，模拟器合成接口冒烟 **11 项通过**；Android 没有查询到可用调试设备。没有代替用户登录开发者账号、开启安全设置或上传发布。

静态检查、Node 合成测试和真实 MySQL/HTTP 合成账号验证，不等于三端运行成功。真实账号的登录、今日训练和图表展示仍需授权测试账号与最新工具链。

## 本地验证记录（2026-11-25）

| 检查 | 实际结果 |
| --- | --- |
| `npm --prefix mobile run verify` | TS/SFC 静态检查通过；视觉与路由保护补充后 36 passed、0 failed、0 skipped |
| 后端定向回归 | 90 passed、0 failed、0 skipped，5.09 秒 |
| 隔离 MySQL、HTTP 与新增 HTTPS 回归 | 64 passed、0 failed、0 skipped，8.22 秒 |
| Mobile TS 客户端 → HTTPS/TCP → FastAPI → MySQL | PASS，1 个集成测试中 12 项断言；不是 uni.request 真机网络测试 |
| 现有 Web Typecheck | 通过 |
| 现有 Web Vitest | 284 passed、0 failed、0 skipped |
| 现有 Web 生产构建 | 通过，12.09 秒；保留大包体积及依赖注释警告 |
| 微信小程序开发模式编译 | PASS，HBuilderX 5.34，8 个页面，更新详情后 ready 7.542 秒 |
| 微信模拟器合成接口冒烟 | PASS，11 项检查，无捕获到的运行异常；不是真实后端/模型测试 |
| 微信真机及真实后端业务 | 未执行，仍需测试后端与授权账号 |
| Android Vapor 开发模式编译 | PASS，字节码目标，8 个页面，更新详情后 ready 8.677 秒；不是 APK 打包或安装 |
| Android 真机运行 | BLOCKED，设备列表未返回可用设备 |

上述分组有重叠用例，不相加作为独立覆盖数。后端组覆盖 Mobile、Security Hardening、MCP Contract、Coach 分类与 Validator；MySQL 组覆盖 Mobile 及既有 MCP Facts v3/v3.1。MySQL 使用本机 3307 的隔离 `gaitlogic_test_*` 数据库与合成账号，不使用日常或生产数据。

HTTPS 验收运行真实 Auth/Mobile 路由与每请求独立数据库 Session，复用编译后的 ApiClient/AuthSession，Node 测试专用 HTTPS transport 验证完整证书链及主机名。临时 CA 只传给该测试客户端，不修改系统信任、不关闭 TLS 验证。覆盖错误密码、登录/JWT、分页、汇总/日序列一致性、多活动选定、日期限制、身份恢复、退出、账号切换隔离及 MCP Token 拒绝。该隔离应用未挂载全量生产启动流程，登录限流不在此测试范围；真实 Provider 没有参与。

首次新增 HTTPS 测试因把登录的 `last_login_at` 更新误当成训练写入而失败；按既有登录契约修正为只允许两次该字段更新，训练/恢复读请求仍禁止写入，随后组合重跑通过。临时账号、库和本地监听均已清理，测试密钥只在临时目录；凭据通过子进程 stdin 传递，不进入命令行、报告或 Git。

静态工具实际使用 TypeScript 5.9.3、Vue SFC Compiler 3.5.35；实际编译工具为 HBuilderX 5.34.2026102909，Vite 插件 5.34.2026102821.2458，UTS 插件 5.34.2026102820.3709，Vapor 运行插件 5.34.2026102817.4212。小程序日志显示 VDOM，Android 独立日志明确显示蒸汽模式及字节码目标。仓库没有独立 Web lint 命令，因此只记录已有 typecheck、Vitest 和 build，不声称 lint 已通过。

Android 首轮编译暴露 `scroll-x/scroll-y` 不受 Vapor 支持，已统一使用官方 `direction` 属性并新增防回归测试；修复后的两端编译没有再次出现该警告。接口依据：[scroll-view 官方属性](https://doc.dcloud.net.cn/uni-app-x/component/scroll-view.html)。

模拟器通过：登录页布局、错误密码提示、无计划实际训练、竖向滚动、训练详情导航、活动级 RPE/原始圈语义、图表挂载及缺失提示、Gilo 空态、创建会话及 JSON 消息、个人身份展示、退出清理。均通过官方自动化 SDK 在模拟器运行现有编译产物，`wx.request` 返回固定合成响应，未访问真实服务。它补充 UI/跨端运行证据，不能替代 MySQL/HTTP 集成、真实 Coach 或真机验收。

训练详情显示已存储的配速、平均/最大心率、步频、功率、暂停与来源，并将活动 RPE 限于 1–10 的有效值；不将未知值转为 0，不将活动评分作为整堂评分。原始圈按需展开，保留原始序号，不参与客户端加总；规范化结构完整性单独提示。

测试过程曾因自动化 mock 返回格式、virtualHost 选择器和热更新脚本/模板错配失败；仅清理本测试工程的编译缓存并关闭重开后，重新连接自动化完整通过，未清理真实账号存储或其他工程。清理逻辑使用正常退出交互，不再依赖开发工具内部模块 require 的上下文。未通过放宽业务校验解决。脚本有界等待，拒绝覆盖已有登录，完成后清除合成身份和 mock 并恢复原 API 配置。

基础工程验收没有执行生产操作；后续获授权只部署五文件 REST/MCP 路由补丁，没有修改生产配置、执行 Garmin 同步、付费模型调用或数据库迁移。已跨过两端开发模式编译门槛，但没有完成设备业务验收，不能称为 Mobile v0.1 完整验收。

## 文档

- [架构与审计](ARCHITECTURE.md)
- [兼容性矩阵](COMPATIBILITY.md)
- [运行与测试](DEVELOPMENT.md)
- [后续路线及发布门槛](ROADMAP.md)

## 隐私

普通 uni 存储**不是 Keychain/Keystore**；App 发行前需评估凭据保护、设备备份和锁屏风险。退出清除本地身份和请求，不代表服务端 JWT 全端撤销已实现。

可开源工程、通用适配、类型、合成测试及脱敏报告。真实训练/恢复/聊天、用户资料、Token、Garmin/模型/微信凭据、签名、生产配置和日志必须私有。生成目录与本地配置已排除。
