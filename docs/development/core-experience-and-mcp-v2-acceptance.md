# Core Experience 与 MCP 事实升级：统一验收

## 范围与环境

基于 `066f1dc`，开发分支 `codex/core-experience-unified`。本轮不自动合并、推送、部署或执行生产迁移，不修改训练阈值、确定性决策、Garmin 同步方式或正式计划审批。

现有未提交的 `scripts/upgrade_v0130_adaptive_plan.py`、部署审计文档及脚本不属于本轮改造，保持原状。

## UI 变更

- 主导航收敛为今日、计划与日历、记录与趋势、AI 教练、我的与设备；原有深层路径保留。管理后台仅对原有管理员条件显示。桌面多标签默认关闭，仍可手动打开。
- 首次引导支持创建 AI 草稿、导入既有计划、仅记录训练三条路径；设备可稍后连接，可回退、继续和跳过。只在浏览器保存按账号区分的步骤与选项，不保存健康信息或对话。
- 今日页先展示课表与下一步，数据依据折叠；重要规则及恢复风险仍在正文展示。无课表不等于休息，无加载结果不等于没有训练。历史日期不会展示今天的恢复评估。
- 记录页增加最多十二条实际设备活动，独立于周期统计；来源、关联与计划语义保持区分。手动日志仍经原有日志入口访问，不伪称设备列表覆盖全部训练。
- 同步页突出当前/最近任务、真实计数、错误和处理方向，历史表折叠。防重复重试、明确轮询暂停；从 KeepAlive 页面离开也会停止轮询。取消保留原后端语义。
- 周复盘区分事实、解释、建议和确认。`跑量完成比（整周）`明确是实际/整周计划跑量，不是到期课程完成率。拒绝、确认与版本校验保留。当前生成流程仍要求下一训练周；不伪装已支持无目标周的独立生成。
- 今日、计划、记录和周复盘可带有界 topic/date 进入 Coach；只在用户点击后准备新对话，发送仍需显式操作。问题由后端重新获取授权事实，不把 URL 内容当训练证据。未发送内容先确认，warnings 保留，limitations 可展开。
- 统一卡片、按钮层级、焦点样式、移动端安全区域与减少动画偏好。

## MCP 六个只读工具

既有四个工具保留，增加 `get_training_detail(record_ref)` 和 `get_recovery_trend(days)`。所有工具显式声明只读、非破坏、非开放互联网。

### 训练分页与兼容

- 原有不带 cursor 的 1–28 天调用保留 registry-backed 兼容路径。补充计划分类来源，不能把计划类型直接宣称为实际训练类型。
- 完整 v2 分页：首次传 `cursor="first"`；或使用大于28天窗口、显式 `start_date/end_date`。支持1–90天、每页1–20条。随后保持 days/limit/date 参数一致，传返回的 `next_cursor`。
- 游标签名绑定用户、日期、页大小和事实快照，15分钟有效。事实发生变化返回 `CURSOR_STALE`，调用方从第一页重新开始，不能拼接不同快照。
- 汇总覆盖完整查询窗口，不可将每页汇总相加。`details_complete`只对一次返回完整窗口为true，最后一页不代表已独立返回完整窗口。
- 最多5000条候选记录；超过上限拒绝，不静默截断。当前读取会在内存中构建该有界窗口，不是面向海量记录的数据库游标实现。
- 新分页投影的 `rest_days`是计划休息且无已记录正距离跑步的日期数，并非已确认的生理休息；兼容路径的原值仍是历史计划口径。`planned_rest_days`与说明用于区分。
- `source`表示记录字段来源；`origin_source=UNKNOWN`表示尚未验证原始来源。不得由MANUAL推断没有Garmin活动，也不得把有记录当成独立验证。

### Runner State

不改变原状态和风险。MCP只公开固定训练数值白名单及对应证据；健康动态字段仍不混入旧授权。增加评估充分性和缺失证据。只有状态可用且有允许公开的证据、无已知缺口时才标记ASSESSED，否则是PARTIALLY_ASSESSED或INSUFFICIENT_DATA，不生成概率意义的confidence。

### 恢复授权

`mcp:recovery:read`是独立可选权限。授权页需要额外勾选；旧`mcp:read`令牌无法读取恢复历史，刷新令牌不能扩大权限。第三方客户端需重新发起包含此scope的用户授权。恢复查询仅SELECT已保存的日历日记录，不调用Garmin，不创建恢复评分；缺值保留null、缺日单列，数据域时效用记录日期/更新时间/同步时间区分。每项来源只返回受限枚举，真正测量时刻未知时为null。

没有已验证个人HRV基线时`baseline=null`。主观疲劳不是session RPE，不自动把聊天内容写入健康记录。

历史 `hrv_metric` 可能存的是测量类型；仅明确的毫秒单位映射为 `hrv_unit=MS`，其余保留原 metric，单位为 null。授权刷新支持缩小范围，缩小后的刷新令牌不能再扩大回原权限。

### 单次详情

仅支持稳定的`workout_log:<id>`，按认证用户查询。先检查日志归属，再检查关联活动归属；跨用户和不存在均返回RESOURCE_NOT_FOUND。最多100段真实持久化laps，多余标记不完整，不按配速生成分段或推断热身/主课。没有分段就明确缺失。心率质量未验证时UNKNOWN，不能凭单段低心率判断恢复良好。

### 检索错误

未启用、未配置索引和语料不可用映射为KNOWLEDGE_INDEX_UNAVAILABLE；内建超时映射RETRIEVAL_TIMEOUT；无匹配仍是成功的EMPTY，而非服务错误。不输出配置路径、凭据、查询或底层异常。

**部署边界**：本轮未替服务器创建真实知识索引、修改Qdrant或启用付费Embedding服务，因此不能把错误分类修复称为线上RAG已恢复。真实检索需要另行核对已授权环境中的索引与Provider配置。

## 用户统一验收清单

1. 桌面和手机主导航可到达原有全部功能；普通用户不见管理入口。
2. 新账号可选择三条开始路径；中途退出再进入可继续；换账号不会继承步骤。
3. 无计划时仍能访问设备活动与导入，缺课表不会显示“应休息”。
4. 有计划时先看到课程；重要风险可见；记录已有距离和RPE不因打开快速打卡被覆盖。
5. 同步成功/部分成功/失败/取消/无变化均有可理解下一步，失败不显示成功；离开后没有持续轮询。
6. 周复盘展示选定周事实、保留历史记录；切换训练周不会被迟到响应覆盖。计划调整可不采用、可确认、可反馈，确认仍有服务端校验。
7. 从页面进入Coach不会自动发送消息；只有发送后查询真实授权事实，不直接应用计划。
8. 使用`get_recent_training(days=30,cursor="first")`翻完所有页，汇总一致且不重复；改变用户/窗口/签名/事实后游标被拒绝。
9. 原授权读取恢复工具返回权限不足；重新授权恢复scope后可查询；不同用户不能读取彼此记录。
10. 有分段只返回已有laps，无分段明确false；真实原始内容、GPS与自由文本日志不进入工具结果或测试夹具。

## 执行命令

后端：`python -m pytest -p no:cacheprovider -q tests/test_mcp_facts_v2.py tests/test_mcp_http.py tests/test_mcp_server.py tests/test_mcp_knowledge.py tests/test_mcp_oauth_routes.py`

真实MySQL：设置`GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL`到本机`gaitlogic_test_*`隔离库，然后运行`tests/test_mcp_facts_v2_mysql.py`和既有OAuth测试。禁止使用日常或生产库。

前端：在web目录运行`npm run typecheck`、`npm run test`、`npm run build`。

浏览器：`tools/core_experience_smoke.cjs`需要Playwright、运行中的本地前端、`UI_ARTIFACT_DIR`私有截图目录；可通过`UI_BROWSER_CHANNEL=msedge`使用已安装Edge。仅拦截合成API，不连接生产账号。不能把该检查称为真实Provider全链路通过。

## 本轮实际验证（2026-11-05）

| 验证 | 结果 | 边界 |
| --- | --- | --- |
| 前端 Typecheck | PASS | 无类型错误 |
| 前端 Vitest | 147 passed / 27 files | 既有组件测试存在未注册 el-tag 的 Vue 警告 |
| 前端生产构建 | PASS | 存在大于500KB的 bundle 警告，未宣称完成首屏性能优化 |
| 后端定向回归含真实 MySQL | 79 passed / 2 skipped | 两项既有Auth测试使用独立的默认MySQL连接，未连接成功；非完整 pytest 全仓回归，不将 skipped 算作通过 |
| 独立真实 TCP OAuth/MCP 双用户回归 | 1 passed | loopback + 合成用户 + 隔离 MySQL，包含资源绑定与撤销 |
| 历史 OAuth Schema 部分迁移恢复、重复升级 | 1 passed | 独立空测试库；不操作开发或生产数据库 |
| 桌面与手机浏览器 | 16 个场景通过 | 7条页面路径各2个尺寸，另各1个有计划场景；合成API，非真实Garmin/LLM |
| git diff --check | PASS | 原有无关修改保持未提交 |

测试库只使用本机3307端口的 `gaitlogic_test_*`；集成数据均为合成数据，测试后只清理本次创建的用户与关联记录。未查询真实训练与健康记录。

本次未运行真实 Garmin 同步、DeepSeek 分析或线上 ChatGPT 客户端验收。未进行生产结构变更；新增字段均为响应投影或沿用已有OAuth scopes JSON，无新增业务表迁移。

浏览器截图和构建产物保存在仓库外的私有验收目录，不纳入 Git。代码仍在 `codex/core-experience-unified` 工作区，等待用户统一验收，不自动提交、合并、推送或部署。
