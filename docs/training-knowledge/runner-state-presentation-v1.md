# Runner State Presentation v1

## 页面路由和入口

当前训练状态页面路由为 `/runner-state`，页面名称为“训练状态”。入口位于“我的”页面和训练统计页面；移动端底部导航仍保持今日、日历、计划、分析、我的五项。

## 页面组件结构

- `RunnerStateView`：请求编排、加载/错误/刷新状态和页面信息层级；
- `RunnerStateSummary`：确定性综合摘要；
- `RunnerStateCard`：四类状态卡片；
- `RunnerStateRiskList`：风险排序、提示和查看入口；
- `RunnerStateMetrics`：7/28 天核心指标；
- `RunnerStateEvidence`：Evidence、未参与信号、高级 Reason Code；
- `RunnerStateDataQuality`：数据质量分项和 limitations。

状态映射、摘要模板和格式化函数与组件分离，页面不解析复杂推断规则。

## API 调用关系

页面只调用：

```text
GET /api/runner-state/current
```

响应为 `{ "snapshot": {} }`。刷新只是重新请求当前状态，不保存快照、不写数据库、不创建历史记录。接口失败时，初次加载显示错误页；如果已有成功结果，则保留旧结果并提示刷新失败。

## 四类状态中文映射

### 跑量趋势

`DECREASING → 下降`，`STABLE → 稳定`，`INCREASING → 增长`，`SPIKING → 明显增长`，`UNKNOWN → 暂无法判断`。

### 训练一致性

`LOW → 近期训练执行波动较大`，`MODERATE → 近期训练执行较稳定`，`HIGH → 近期训练执行稳定`，`UNKNOWN → 暂无法判断`。

### 疲劳信号

`NORMAL → 暂未发现明显压力信号`，`ELEVATED → 训练压力信号有所增加`，`HIGH → 多项训练压力信号同时出现`，`UNKNOWN → 数据不足，暂无法判断`。第一屏不展示 fatigue score。

### 训练阶段

`BASE → 基础期`，`BUILD → 建设期`，`SPECIFIC → 专项期`，`PEAK → 峰值期`，`TAPER → 减量期`，`RACE → 比赛期`，`RECOVERY → 恢复期`，`UNKNOWN → 未设置`。

## 综合摘要模板

摘要由前端集中模板根据后端状态选择，不调用大语言模型、不创建综合分数：

- “近期训练整体较稳定”；
- “近期训练状态出现一些变化”；
- “近期训练压力有所增加”；
- “当前数据不足，暂无法完整判断”。

摘要只负责表达已有状态，不能读取 fatigue score 或基础指标重新推断状态。

## 风险提示

仅在 `risk_flags` 非空时展示，并按 `ATTENTION → WARNING → INFO` 排序。每项显示中文标题、后端 message、建议检查项、受限建议动作和 Evidence。页面只有“查看训练计划”和“查看最近训练”，没有自动调整按钮，也不自行生成风险标记。

## 7 天与 28 天指标

7 天：总跑量、训练时长、训练次数、高强度次数、平均 RPE、计划完成率。

28 天：总跑量、周均跑量、训练次数、活跃 7 日桶、关键课次数、高强度距离比例、计划完成率。

空值统一显示“暂无数据”；真实 0 保持显示为 0。距离、分钟、比例、次数和 RPE 由集中格式化函数处理。

## Evidence 和 skipped signals

判断依据折叠区显示指标、实际值、窗口、阈值、单位、来源、是否参与和规则集版本。`evidence_coverage` 显示为“证据覆盖程度”。Reason Code 只在高级详情展示。

`skipped_signals` 使用中文名称显示，并明确说明因对应数据不足而未参与判断，不将其显示为风险。

## 数据质量展示

数据质量分项包括：完整度、有效训练数量、距离覆盖、时长覆盖、RPE 覆盖率、心率覆盖率、计划数据情况和 limitations。数据完整度不是状态准确率或预测概率。

## UNKNOWN 展示

UNKNOWN 使用中性图标、文案和标签。训练阶段 UNKNOWN 显示“未设置”；推断 UNKNOWN 显示数据不足。UNKNOWN 不触发 API 错误页，也不使用危险色。

## 非医疗化措辞

页面声明只用于训练管理辅助，不构成医疗诊断、伤病判断或治疗建议。提示使用“建议结合体感检查恢复情况”“建议复核后续训练安排”，禁止使用“即将受伤”“危险”“过度训练”等结论。

## 移动端适配

桌面状态卡片双列，平板和移动端变为单列；指标区按宽度降为双列或单列；长 Evidence、来源和 Reason Code 允许换行；按钮在移动端扩大为适合触摸的整行布局。页面保留底部导航空间，不增加第六个导航项。

## 当前状态与历史快照边界

当前页面展示请求时即时计算的状态。浏览器中保留的上次成功结果只用于刷新失败降级，不是历史快照。C1 没有快照表、写入接口或历史趋势；C2 才单独设计和实现历史状态快照。

## 完全虚构的数据示例

```json
{
  "identity": {
    "runner_id": 900001,
    "calculation_window_end": "2026-07-15",
    "generated_at": "2026-07-16T10:00:00+08:00"
  },
  "volume_trend": {
    "state": "STABLE",
    "previous_21d_weekly_average_km": 36.0,
    "volume_ratio": 1.20
  },
  "training_consistency": {
    "state": "HIGH",
    "basis": "PLAN_COMPLETION",
    "evidence_coverage": 1.0
  },
  "fatigue": {
    "state": "NORMAL",
    "available_signal_count": 4,
    "total_signal_count": 5,
    "evidence_coverage": 0.8,
    "skipped_signals": ["RPE_CHANGE"]
  },
  "risk_flags": []
}
```

示例仅用于界面开发和测试，不对应任何真实用户。
