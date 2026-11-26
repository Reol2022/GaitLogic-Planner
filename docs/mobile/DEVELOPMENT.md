# 本地开发与验证

1. 本机已核验 HBuilderX 5.34.2026102909（`D:\HBuilderX`）及微信工具 2.02.2609250；后续升级需重新核验。
2. 打开 `mobile/`，识别为 uni-app x，确认 Vapor、样式隔离 2。保留微信 AppID，DCloud AppID 由工具/平台分配，不虚构。
3. 准备 HTTPS 测试后端、原账号与三条 Mobile GET。2026-11-25 三个 GET 已以授权最小补丁部署生产；其他实例需核对 OpenAPI，404 不是空训练。
4. HBuilderX 运行到微信工具，配置合法 request 域名与基础库；不关闭正式 TLS/域名校验。
5. Android 使用当前基座与“运行到手机/模拟器”，准备设备/SDK/adb。iOS 单独准备。此处不编造已验证的 CLI/打包命令。

普通登录只填写账号与密码；production 默认使用已确认的 HTTPS 后端。测试地址在展开的连接设置中调整，不覆盖已保存的自定义地址。example.invalid 仍拒绝发送 Token。开发/生产 Token 命名空间分离；真机 localhost 不是电脑。地址变更需退出并清空栈。

AppSecret、模型/Garmin 凭据、Token、私有配置及签名不提交；App Token 的 Keychain/Keystore 适配尚未实现。

## 可执行检查

新增工作区验证：

```powershell
npm --prefix mobile run verify
npm --prefix mobile run test:components
```

组件回归复用 `web/` 已安装的 Vue/Vitest/jsdom 开发依赖；先安装 Web 锁文件对应依赖。它编译实际 `.uvue` 源码并使用合成接口，不等于微信或 Android 设备验收。基础静态检查不包含这个独立测试目录，组件测试由自己的 Vite 转换执行。

原生合成冒烟默认如实标记表单选择器限制为 BLOCKED，不能将整组 PARTIAL 写成 PASS。测试必须在没有真实登录的本地模拟器运行，且不会替换已有登录。完整迁移范围见 [Web 迁移清单](WEB_MIGRATION.md)。

已执行成功的小程序开发模式编译（PowerShell 必须用完整路径，避免 `cli` 与系统别名冲突）：

```powershell
& 'D:/HBuilderX/cli.exe' open
& 'D:/HBuilderX/cli.exe' project open --path 'E:/我的项目/Gaitlogic-planner/mobile'
& 'D:/HBuilderX/cli.exe' launch mp-weixin --project 'E:/我的项目/Gaitlogic-planner/mobile' --compile true
```

产物为 `mobile/unpackage/dist/dev/mp-weixin/`（已忽略），在微信开发者工具中导入该目录，不是源 `mobile/`。编译不代表模拟器或真机运行，也不代表生产发行。CLI 有时在报错时仍返回退出码 0，验收必须检查实际日志和产物。

本机已配置 DCloud AppID 并安装 Vapor 运行插件。已成功执行的 Android 本地开发编译：

```powershell
& 'D:/HBuilderX/cli.exe' launch app-android --project 'E:/我的项目/Gaitlogic-planner/mobile' --compile true
& 'D:/HBuilderX/cli.exe' devices list --platform android
```

生成开发字节码不代表生成可安装 APK；本轮设备列表没有返回设备。后续运行仍需手机或模拟器及对应调试授权。不要用微信 AppID 填入根 `appid`。微信工具服务端口已经用户开启并核验生效；如果配置了 CLI Token，留在本机私有环境中，不发送到聊天或仓库。正式运行仍需合法 HTTPS request 域名与测试后端。

## 微信模拟器合成接口冒烟

使用官方 `miniprogram-automator` 0.13.0，仅安装于已忽略的私有测试工具目录，不进入 Mobile 运行依赖。该 SDK 安装输出包含旧传递依赖弃用提示，不将其打包进小程序/App。

```powershell
npm install --prefix .audit-private/mobile-tools --cache .audit-private/npm-cache --package-lock=false --ignore-scripts miniprogram-automator@0.13.0
& 'D:/微信web开发者工具/cli.bat' auto --project 'E:/我的项目/Gaitlogic-planner/mobile/unpackage/dist/dev/mp-weixin' --auto-port 9420
$env:GAITLOGIC_MINIPROGRAM_AUTOMATOR_MODULE=(Resolve-Path '.audit-private/mobile-tools/node_modules/miniprogram-automator').Path
node mobile/tools/smoke-wechat.cjs
```

自动化端口仅用于本机开发，不开放公网。脚本拒绝覆盖已登录的用户，测试数据全部合成，`wx.request` 通过官方自动化 mock 返回固定响应；不调用 Garmin、模型或真实 REST 服务。成功记录 11 项检查，测试结束恢复 API 地址、清除合成 Token/内存身份及 mock。每项等待有界，失败应检查私有工具控制台，不把模拟器 mock 成功称为真实后端验收。

HBuilderX 重新生成产物时若发现脚本/模板热更新错配（例如 RPE 显示为状态栏像素），只对当前生成工程清理 `compile` 缓存，然后关闭、`open` 重开、再启动 `auto`；不要使用 `all`/`storage`/`auth` 清理，也不通过调低业务校验来消除症状。关闭重开期间旧自动化连接失效，需要重新连接。

仓库已安装 Web 开发工具依赖时：

```powershell
npm --prefix mobile run typecheck
npm --prefix mobile test
```

优先使用 Mobile 开发依赖，当前可复用 Web 的 TypeScript/SFC 工具，不复制 Web 业务模块或改变其构建。原生 Vue 由 HBuilderX 提供，不另装旧运行时冒充 Vapor。

typecheck 是入口/页面存在性、Vapor 标记、TS 与 SFC 语法检查，**不是原生编译**。test 在已忽略的 .test-build 编译纯 TS，再运行 Node 合成测试，不访问 Garmin/付费模型。

后端测试为 `tests/test_mobile_api.py`、`tests/test_mobile_api_mysql.py`，使用既有隔离协调器 `scripts.audit.run_isolated`，仅限明确的本机 3307 / gaitlogic_test_* 和受限账号；密码只在环境提供。

## 回归复现命令

```powershell
.venv/Scripts/python -m pytest -p no:cacheprovider -q tests/test_mobile_api.py tests/test_security_hardening.py tests/test_mcp_facts_v31_contract.py tests/test_coach_task_classifier.py tests/test_agent_validator.py
```

安全确认本机隔离实例、通过私有环境变量提供引导连接后，由现有协调器创建专用受限测试账号及隔离库：

```powershell
.venv/Scripts/python -m scripts.audit.run_isolated tests/test_mobile_https_mysql.py tests/test_mobile_api_mysql.py tests/test_mobile_api.py tests/test_mcp_facts_v3_mysql.py tests/test_mcp_facts_v31_mysql.py
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
```

协调器的数据库创建与清理只用于明确隔离实例，不得配置到生产连接。诊断产物留在已忽略的私有目录。

`tests/test_mobile_https_mysql.py` 需要先执行 Mobile verify，生成最新纯 TS 客户端测试产物，并准备 Node、cryptography 和本机隔离 MySQL。测试创建短时 CA/服务器证书，在随机回环端口运行真实路由，调用 `mobile/tools/verify-rest.cjs`；客户端只接受 127.0.0.1 HTTPS，显式验证证书，不改变系统信任。数据库连接、测试账号密码和 Token 不通过命令行或日志传递。

这条链路证明服务端和共享 TS 客户端的真实 HTTPS 协议兼容，不是 uni.request 实现的网络验收；小程序实际网络仍需已部署 Mobile 路由的合法 HTTPS 测试后端、平台 request 域名及授权测试账号。生产最小补丁部署后的无身份请求已命中普通 REST；它不代表真实账号数据展示已完整验收。

## 设备验收步骤（尚未执行）

- 错误密码、正确登录、启动恢复、Token 失效、断网、退出、换账号，不能再看到旧训练/聊天。
- 今日覆盖有计划未做/已做、无计划实际、休息、空数据、部分恢复缺失、Garmin 未连接与失败。
- 分页、多活动选择、分段与范围，不将截断列表求和、不拼接圈。
- 七天柱图、折线、日历和窄屏/切页/长列表；null 不绘成 0，无记录不称休息。
- Gilo 会话/消息、真实进度、取消和断网；只核对原 turn，不自动重发，不假流式。
- 记录编译器、基础库、设备/系统与错误；截图用合成数据或留在私有目录，不把运行步骤写成已通过结果。
