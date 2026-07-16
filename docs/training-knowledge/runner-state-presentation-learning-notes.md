# 跑者状态展示学习说明

## 页面入口在哪里注册

`web/src/router/index.ts` 注册 `/runner-state` 路由。`MyView.vue` 提供移动端“我的”入口，`DashboardView.vue` 提供训练统计入口。移动端底部导航定义在 `AppLayout.vue`，C1 没有修改其五项结构。

## API 从哪里调用

`web/src/api/runnerState.ts` 使用项目统一请求封装，请求 `GET /runner-state/current`。统一 Axios base URL 已包含 `/api`，最终后端路径是 `GET /api/runner-state/current`。该模块没有 POST、PUT、PATCH 或 DELETE 方法。

## `{ snapshot: {} }` 如何映射为前端类型

`web/src/types/runnerState.ts` 按后端 Pydantic Schema 定义 identity、基础指标、派生指标、推断结果、Evidence、风险、数据质量和 metadata。B 阶段新增字段允许 null 或在兼容响应中缺省，页面使用 UNKNOWN 和空值降级，不使用大量 `any`。

## 页面组件如何拆分

页面组件负责请求和信息层级；摘要、卡片、风险、指标、Evidence 和数据质量分别由小组件展示。状态判断逻辑不放在组件中，组件只读取后端状态和集中映射。

## 状态中文文案在哪里维护

所有状态、阶段、风险、动作、Evidence 指标、窗口、信号和常见 Reason Code 文案集中在 `web/src/utils/runnerStateDisplay.ts`。修改术语时必须同步更新映射测试和公开文档。

## 综合摘要如何生成

`web/src/utils/runnerStateSummary.ts` 根据后端返回的 volume、consistency 和 fatigue 状态选择四类确定性模板。它不读 fatigue score，不计算阈值，也不生成新的综合状态。

## 为什么前端不能重新计算 fatigue score

疲劳信号的阈值、可用信号条件和规则集版本属于后端领域规则。如果前端重复计算，会产生两套实现、版本漂移和难以追踪的判断。前端可以显示 Evidence 覆盖程度，但不能根据 score 改写状态。

## 为什么前端不能自行生成 risk flag

风险标记必须包含受审查规则、Evidence 和版本。前端仅排序和翻译后端 flags；不能根据颜色、跑量或状态自行补旗，也不能把数据缺失当风险。

## Evidence 如何展示

Evidence 在折叠区展示 metric、value、window、threshold、unit、source 和 used。普通模式使用中文指标名；Reason Code 位于高级详情；规则集版本显示在底部。长内容通过换行和响应式单列保证可读。

## skipped signals 如何展示

疲劳结果的 `skipped_signals` 映射为中文标签，并说明“因对应数据不足而未参与本次判断”。Reason Code 可以进一步解释是 RPE、计划还是基础数据不足。

## 刷新失败为何保留旧结果

短暂网络错误不应让用户失去刚才仍可阅读的状态。页面在刷新开始时不清空 snapshot；失败后显示提示并保留旧结果。保留结果只是界面降级，不保存数据库，也不构成历史快照。

## 如何增加一个新的展示字段

1. 确认后端真实 Schema 已提供字段；
2. 更新 `runnerState.ts` 类型；
3. 在对应组件增加纯展示项；
4. 使用集中格式化函数处理 null 和 0；
5. 增加虚构 Fixture 和组件测试；
6. 检查桌面和窄屏换行；
7. 不在展示层补造后端没有的推断结论。

## 如何修改移动端布局

优先在具体组件 scoped CSS 的 `900px`、`768px`、`520px` 或 `420px` 断点调整网格。保持底部导航留白、按钮触摸面积、Evidence 单列和无横向滚动。不要通过隐藏重要 Evidence 来解决拥挤。

## 如何增加对应测试

Vitest 配置在 `web/vitest.config.ts`。工具测试覆盖映射、摘要和格式化；组件测试覆盖 Evidence、风险、指标和质量；页面测试 mock 现有 GET，覆盖加载、错误、刷新和旧数据保留。Fixture 必须完全虚构，不包含真实账号或训练记录。

## 项目负责人验收清单

- `/runner-state` 路由和两个入口存在；
- 移动端底栏仍为五项；
- 只调用 current GET；
- 第一屏不显示 fatigue score；
- BUILD 为“建设期”，PEAK 为“峰值期”；
- Reason Code 仅在高级详情；
- 显示“证据覆盖程度”，不写准确率；
- UNKNOWN 为中性状态；
- 缺失值与真实 0 可区分；
- 风险按优先级排序且无自动调整按钮；
- 刷新失败保留旧结果；
- 四类视口无横向溢出，长 Evidence 可读；
- 测试、构建、C1 类型检查和安全边界检查通过；
- 没有数据库迁移、历史快照、大模型或真实用户数据。
