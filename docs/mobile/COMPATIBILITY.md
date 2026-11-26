# Mobile 兼容性记录

2026-11-25 复核：本机 HBuilderX `5.34.2026102909`；微信工具登记 `2.02.2609250`。Vite 插件 `5.34.2026102821.2458`，UTS 插件 `5.34.2026102820.3709`。未用传统 uni-app 工程替代。

| 验收项 | 微信小程序 | Android | iOS |
| --- | --- | --- | --- |
| 工程编译 | PASS，HBuilderX 开发模式编译 8 个页面 | PASS，Vapor 字节码开发目标，8 个页面；不是 APK 打包 | NOT RUN，无本轮设备/编译环境 |
| 设备登录和认证 | 模拟器合成接口登录/错误提示/退出通过；真实后端与真机未验证 | 未验证 | 未验证 |
| uni.request、取消、存储 | 模拟器 mock 请求及退出清理通过；真实网络/设备取消未验证 | 适配器已写，设备未验证 | 同左 |
| 图表、日历与长列表 | 模拟器图表挂载、缺失提示、竖向滚动通过；日历和长列表性能未验收 | 未验证 | 未验证 |
| 多活动详情 | 模拟器选择单条活动、活动 RPE、原始圈展开与结构缺口提示通过，合成响应 | 编译通过，未运行 | 未验证 |
| Gilo JSON 和进度 | 模拟器创建会话与合成 JSON 消息通过；真实模型/进度并发未验证 | 契约已接，设备未验证 | 同左 |
| 文本流 | 后端无此协议，真实非流式回退 | 同左 | 同左 |
| Markdown/切页/内存 | 组件已写，无真机测量 | 同左 | 同左 |

微信和 DCloud AppID 已配置，不代表合法域名、基础库、主体或审核通过。HBuilderX 的 Android 设备查询未返回可用设备，因此未安装或运行。iOS 不作本轮硬性验收条件。

小程序 `launch mp-weixin --compile true` 已成功生成 `mobile/unpackage/dist/dev/mp-weixin/`，AppID 与源配置一致；没有上传。CLI 的 `publish mp-weixin --upload false` 要求登录，未执行登录。小程序编译日志的 VDOM 指该平台目标，不代表 Android Vapor 验证。

微信服务端口经用户配置后已生效，已打开本地项目并建立自动化连接，11 项合成接口 UI 冒烟通过；没有修改其安全设置。Android 首次因缺 AppID/插件阻塞；配置完成并允许官方插件安装后，`launch app-android --compile true` 已成功生成 `app-service.js`、配置和 `bytes/`。未生成发行 APK，也未安装运行。

另有编译后的 TS API/Auth 客户端通过真实 HTTPS/TCP 访问隔离 FastAPI/MySQL 的 12 项链路断言；传输为 Node 专用测试适配器，不计作微信、Android 或 iOS 的 uni.request 网络验收。未修改系统 CA、平台 HTTPS 校验或生产服务器。

Android 首轮实际编译报告旧 `scroll-x/scroll-y` 属性不受支持；已改为 `direction` 并通过两端重新编译，增加源模板防回归测试。编译通过不能证明真机滚动、内存或安全区域表现正确。

当前可执行 TS/SFC 静态检查、Node 合成测试、MySQL/HTTP 合成账号测试；三者均不是小程序/Android 编译或个人账号真机验收。真实数字见交付报告，不把 skipped/超时当 passed。

UI 使用原生组件与轻量布局图表，无 WebView、浏览器 ECharts、Emoji 导航或未经审查 SDK。Pinia、uni-ui x 尚未本机验证，未引入为已兼容依赖。Mobile v0.1 尚未完整验收。
