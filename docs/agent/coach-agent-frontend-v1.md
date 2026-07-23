# Coach Agent 前端实现 v1

## 实现结构

- 页面：`web/src/views/CoachAgentView.vue`
- 类型：`web/src/types/coachAgent.ts`
- API：`web/src/api/coachAgent.ts`
- 显示映射：`web/src/utils/coachAgentDisplay.ts`
- 会话裁剪：`web/src/utils/coachAgentConversation.ts`
- 组件：`web/src/components/coach/`

路由为 `GET /coach` 的前端页面，实际业务请求只调用：

```text
POST /api/coach/query
```

请求只包含 `message`、公开 Intent 和可选的公开短 conversation context。认证由共享 Axios Client 注入；页面不接触 Token，也不实现自动重试。

## HTTP 错误

| HTTP | 用户文案 |
| --- | --- |
| 401 | 登录状态已失效，请重新登录 |
| 403 | 该教练能力暂未开放 |
| 400/422 | 输入内容不符合要求 |
| 429 | 请求过于频繁，请稍后再试 |
| 503 | AI 教练暂不可用 |
| 网络错误 | 暂时无法连接服务，请稍后重试 |

共享拦截器仍负责认证失效流程。Coach API 使用 `skipErrorMessage`，由页面显示固定安全错误，不把服务器异常正文写入 UI。

## 组件职责

- `CoachTodayRecommendationCard`：优先显示确定性 decision、计划状态、风险、数据质量和 Evidence；
- `CoachSafetyNotices`：默认显示 warnings，并区分数据、Context、工具和模型限制；
- `CoachAnswerCard`：只在 SUCCEEDED/DEGRADED 显示正文，纯文本渲染；
- `CoachToolSummary`：默认折叠，只显示中文工具名、状态和 safe error code。

展示组件不调用 API，也不计算规则、risk flag 或训练指标。

## 会话生命周期

`CoachAgentView` 持有最多 8 个 `CoachConversationTurn`。超过上限删除最早轮次并显示裁剪提示。发送 Context 时进一步限制单项和总字符数。清空按钮只清理内存；刷新页面不会恢复。

## 导航与布局

- `/coach` 使用既有路由守卫；
- 桌面侧栏增加“AI 教练”；
- “我的”首页增加快捷入口；
- 移动底栏未改，仍为原有五项；
- 360px、768px 和 1280px 通过响应式布局规则覆盖。

## 测试

自动测试覆盖 API 字段与错误、所有固定枚举映射、五类 decision、五类计划状态、回答状态、XSS 纯文本、warnings/limitations、工具摘要、会话裁剪、重复提交、错误重试、清空、导航和无浏览器持久化。

所有 Fixture 均为虚构内容，未访问真实 Provider、用户或训练数据。

## 当前限制

没有 Weekly Review Agent、RAG、写工具、长期记忆、Streaming、WebSocket、多 Agent、文件或语音输入。页面不会生成或修改训练计划。
