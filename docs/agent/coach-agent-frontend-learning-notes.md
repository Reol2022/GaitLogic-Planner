# Coach Agent 前端学习说明

## 为什么不是普通聊天页面

普通聊天界面容易让用户把自然语言正文误认为系统决策。GaitLogic 的权威顺序是训练事实、Runner State、Rule Engine、Agent 编排、LLM 表达。因此页面先显示 `today_recommendation`，再显示 warnings/limitations，最后才显示模型解释。

## 为什么规则结果优先

`decision` 已由后端确定性规则生成。前端只通过 `coachAgentDisplay.ts` 翻译它，不能根据 answer、risk score 或用户文字重新推断。修改映射时必须保持：PROCEED 不等于绝对安全，CONSIDER_ADJUSTMENT 不等于计划已修改，REST_OR_RECOVERY 不能弱化，UNKNOWN 不能改成可执行。

## 为什么 DEGRADED 仍可用

Provider 失败时，后端可以用已有规则和事实生成确定性 Fallback。`DEGRADED` 表示模型解释不可用，但规则建议仍有效。页面因此保留完整结果，并用固定提示说明来源，不把它渲染成失败页。

## 为什么不持久化会话

问题与回答可能包含训练上下文。D1 不需要长期记忆，因此数据只放在 Vue `ref` 中，不进入浏览器存储。刷新后清空能降低共享设备和 XSS 场景下的暴露范围。

## conversation context 如何裁剪

`buildCoachConversationContext` 只提取用户问题和回答的公开 summary/answer，从最新内容向前保留；每项截断到 900 字符，总字符不超过 6000。页面最多保留 8 轮，超出时删除最早内容并提示用户。不要把 tool calls、Trace、warnings 的内部结构或完整 response 放入 Context。

## 为什么不展示完整 Tool Result

工具结果可能包含大量训练事实或内部结构。公共 API 已只返回工具名、状态和安全错误码，前端进一步使用中文名展示。未知工具显示为“其他安全数据来源”，不会暴露裸内部名称。

## 为什么禁止 v-html

模型文本是不可信输入。Vue 文本插值会转义 HTML，而 `v-html` 可能执行恶意标签或事件属性。答案需要换行时使用 CSS `white-space: pre-wrap`，不要引入未经审计的 Markdown/HTML Renderer。

## 如何处理 429

`queryCoach` 将 429 映射为固定文案，页面保留输入，不自动重放 POST。用户等待后可以手动重试。不要用循环、Axios retry plugin 或计时器自动发送。

## 如何增加 Intent

1. 后端先公开并测试 Intent；
2. 扩展 `CoachAgentIntent`；
3. 补齐 `coachIntentDisplay` 的穷尽映射；
4. 增加固定入口及默认问题；
5. 明确权威数据、展示顺序和安全校验；
6. 增加 API、页面、映射和回归测试。

不能只在前端添加一个任意字符串选项。

## 如何调试 API

优先检查浏览器 Network 的状态码和公共响应状态，不要把完整 request/response 打到 console。401 检查登录态，403 检查 Intent，429 等待限流，503 检查服务启用情况。Provider 原始错误只能在后端脱敏运维日志中排查。

## 如何测试安全展示

- 用包含 HTML 标签的虚构 answer，确认 DOM 中没有对应元素；
- 验证 VALIDATION_FAILED 不显示 answer；
- 验证工具摘要没有 arguments/data/user ID；
- 监控 Storage API，确认页面不写入；
- 验证卸载时取消请求；
- 验证错误后输入仍存在；
- 验证所有状态都有文字，不只靠颜色。

## 项目负责人验收清单

- [ ] 权威建议在 AI 正文之前；
- [ ] NO_PLAN 与 REST_DAY 区分；
- [ ] HIGH warning 默认可见；
- [ ] DEGRADED 可用且来源说明清晰；
- [ ] WEEKLY、Provider、模型、Key 和 Prompt 不出现在功能入口；
- [ ] 页面无 `v-html`、console 日志和浏览器持久化；
- [ ] 发送中不能重复提交，429/网络失败保留输入；
- [ ] 工具摘要默认折叠且仅含安全字段；
- [ ] `/coach` 受登录守卫保护；
- [ ] 桌面和“我的”入口存在，移动底栏未增加第六项；
- [ ] 360/768/1280 布局无横向溢出；
- [ ] 没有计划修改、日志写入、快照或 Garmin 行为。
