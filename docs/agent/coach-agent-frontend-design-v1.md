# Coach Agent 前端产品设计 v1

## 页面定位

`/coach` 页面名称为“AI 教练”，它不是开放式聊天机器人，而是确定性训练系统的解释界面：

```text
确定性规则建议 → 关键依据 → 安全提示与限制 → AI 解释 → 数据来源摘要
```

数据库和业务 Service 提供事实，Runner State 提供状态，Rule Engine 提供 decision，前端先展示这些权威结果。模型回答不能覆盖、弱化或重新计算确定性建议。

## 支持范围

当前公开 Intent：

- `TODAY_RECOMMENDATION`
- `EXPLAIN_RUNNER_STATE`
- `GENERAL_TRAINING_QUESTION`

`WEEKLY_REVIEW` 不出现在页面。当前也没有 RAG、向量检索、写工具、计划修改、长期记忆、Streaming、WebSocket、多 Agent、语音、文件上传或 Provider 配置入口。

## 信息架构

页面包含：

1. 标题、副标题和非医疗/只读边界；
2. 三个固定快捷入口；
3. 多行文本输入、字数限制、发送和清空；
4. 用户问题；
5. 今日建议权威卡片；
6. warnings 与 limitations；
7. AI 解释；
8. 默认折叠的安全工具摘要。

TODAY 卡片展示 decision、planned workout status、risk level、data quality、headline 和 key evidence。`NO_PLAN` 与 `REST_DAY` 必须分开；`UNKNOWN` 是数据不足，不得显示为可以正常执行。

## DEGRADED

`DEGRADED` 是可用结果，不是错误页。页面固定显示“模型解释暂不可用，当前内容由系统规则和已有训练数据生成”，并继续展示后端的确定性建议、warnings、limitations 和工具摘要。

`VALIDATION_FAILED` 不展示被拒绝的模型正文；`REJECTED` 显示能力未开放；`UNAVAILABLE` 显示安全不可用。

## 会话与隐私

会话只存在于当前 Vue 组件内存，最多保留 8 轮。刷新或离开页面即清空，不写 localStorage、sessionStorage 或 IndexedDB。发送后端的 conversation context 只包含裁剪后的公开用户问题和公开回答摘要：单项最多 900 字符，总计最多 6000 字符；不包含 Tool Result、Trace 或 Provider 响应。

## 导航

桌面侧边栏增加“AI 教练”。移动端不增加第六个底栏项，而是在“我的”聚合页增加入口。路由使用现有全局登录守卫，URL 不包含用户 ID、Provider、模型或问题。

## 安全与可访问性

- 不使用 `v-html`，模型内容按纯文本换行；
- 不在 console 输出请求或响应；
- 不显示 Provider、模型、Base URL、Token、Prompt 或技术错误；
- warning 使用 `role=alert`，加载和限制提示使用 live/status 语义；
- 输入框有 label；
- 原生 `details/summary` 提供键盘可操作折叠；
- 状态同时提供文字，不只依赖颜色；
- 页面销毁时 abort 请求，并阻止卸载后更新状态。

## 响应式

1280px 使用三列快捷入口；768px 以下改为单列并为移动底栏保留空间；520px 以下输入操作和状态卡改为纵向，按钮满足触摸尺寸。长问题、答案、Evidence 和错误码均允许断词，不固定答案区域高度。

## 验收标准

- 权威卡片始终先于 AI 正文；
- HIGH warning 默认可见；
- DEGRADED 仍可使用；
- 空输入、超长和重复发送被阻止；
- 请求错误保留输入供手动重试；
- 工具摘要不显示参数和数据；
- 桌面与移动入口可达，底栏保持五项；
- 不存在训练业务写按钮或 Provider 配置入口。
