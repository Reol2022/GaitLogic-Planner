# 跑者状态历史展示学习说明

本文面向项目负责人和后续维护者，解释 v0.10.3-C2.2 的数据流、代码边界与验收方法。

## 1. 当前状态与历史标签如何切换

入口仍是 `web/src/views/RunnerStateView.vue`。页面默认挂载当前状态，只调用 current GET。`historyMounted` 在用户第一次进入历史标签时变为 true，随后历史组件保留在页面中并用 `v-show` 切换，因此切回当前状态不会丢失已加载历史，也不会在首次进入页面时产生历史请求。

## 2. Timeline API 如何计算范围

路由位于 `server/api/routes/runner_state.py`，并注册在动态详情路由之前。`RunnerStateSnapshotService.list_timeline_snapshots` 从注入时钟取得 Asia/Shanghai 业务日期：28 天和 12 周分别减 27、83 天；6 个月按日历月回退并处理目标月份天数，例如 8 月 31 日回退到 2 月最后一天，而不是减固定 180 天。

## 3. 为什么同日只选最后一条

趋势图需要一天一个稳定节点，否则同一日期会在横轴重叠。服务使用相关 `NOT EXISTS` 反连接：只有当同一用户、同一截止日期下不存在更晚 `created_at`，且时间相同时不存在更大 `id` 的记录，候选记录才会保留。`id` 是保存时间相同情况下的确定性兜底，结果再按日期升序返回。该写法可利用现有用户与截止日期索引，也避免依赖数据库窗口函数。

## 4. 为什么原始列表保留全部快照

同一天内状态可能因新训练记录或数据补全而真实变化。趋势只负责每天一个代表点，审计与复盘仍需要每次保存记录。因此列表 API 不折叠日期，并按截止日期、保存时间倒序分页。

## 5. 保存按钮与刷新按钮的区别

刷新调用 current GET，只计算且不落库；保存调用 snapshots POST，后端重新计算并按 C2.1 规则不可变保存。前端不会发送用户、触发方式、版本、payload 或哈希。重复返回是正常的幂等结果，而不是错误。

## 6. 为什么历史详情不能重新计算

详情代表“保存当时的状态”。如果用当前数据或新规则重算，Evidence、limitations 和规则版本将失去审计意义。因此详情只读取保存的 `snapshot_payload`，不会调用 RunnerStateService 或 current API，也不会把旧 payload 套入现行规则。

## 7. 如何复用 C1 组件

`RunnerStateSnapshotContent.vue` 组合 C1 的综合摘要、四类状态卡、风险、核心指标和数据质量组件。当前状态页和历史详情都向它传入一个完整 `RunnerStateSnapshot`，避免复制中文映射、格式化或前端推断逻辑。

## 8. 跑量图数据从哪里来

`distance_7d_km` 直接来自 C2.1 的摘要列。`distance_28d_weekly_average_km` 由后端从同一摘要的 `distance_28d_km / 4` 生成只读字段。前端只展示返回值；`null` 原样进入 ECharts，设置 `connectNulls: false`。文本表格使用同一数组，是图形的无障碍替代。

## 9. 为什么分类状态不用折线图

DECREASING、STABLE、INCREASING 等是类别，不是等距连续数值。映射成 1、2、3 会制造不存在的数学关系。`RunnerStateTimeline.vue` 用标签和变化节点展示完整日期序列，UNKNOWN 使用中性风格。

## 10. 风险事件如何展示

风险标记只读取保存时 payload 中的最小 JSON 字段，并通过单次批量查询补充到 Timeline，不逐条请求详情。前端复用集中式风险标题与严重程度映射，保留保存时的说明。重复出现只说明多个日期都有记录，不推导持续伤病。

## 11. 如何处理请求竞态

`RunnerStateHistoryView.vue` 为 Timeline、列表和详情分别维护 AbortController。范围和列表还使用单调递增请求序号；开始新请求时先取消旧请求，响应落地前再核对序号。详情关闭会增加序号、取消请求并清空详情数据。这样慢响应不能覆盖更新的范围或新打开的详情。

## 12. 如何增加时间范围

1. 在后端 `RunnerStateTimelineRange` 增加枚举；
2. 在 `_timeline_start_date` 明确定义业务日期算法；
3. 在前端 `RunnerStateTimelineRange` 与 `timelineRangeLabels` 同步增加；
4. 增加范围按钮；
5. 补边界、无效参数、竞态和视觉测试。

不要由前端计算开始日期，也不要用近似天数代替日历语义。

## 13. 如何增加历史展示字段

先确认字段是否已有摘要列。已有时用 ORM 摘要查询；仅存在 payload 时，应评估单次批量 JSON 路径读取，不得形成 N+1。扩展后端 Schema、前端类型和虚构 Fixture，再增加缺失值、权限及不泄露完整 payload 的测试。不要为只读展示修改快照哈希或旧记录。

## 14. 如何编写测试

后端重点验证时区边界、范围算法、同日选择、用户隔离、路由顺序、只读行为和字段白名单。前端重点验证懒加载、保存幂等提示、失败保留、缺失值、分类展示、同日列表、详情不可重算、请求竞态及移动端结构。Fixture 必须完全虚构，断言不能依赖真实用户或生产数据库。

## 15. 项目负责人验收清单

- [ ] 首次打开 `/runner-state` 不请求历史；
- [ ] 刷新与保存文案、HTTP 方法和写入语义清楚区分；
- [ ] 28d、12w、6m 边界由后端 Asia/Shanghai 计算；
- [ ] Timeline 每日最后一条，原始列表保留同日全部；
- [ ] 跑量缺失点没有变成 0；
- [ ] 分类状态没有被画成连续数值；
- [ ] 数据质量术语没有变成准确率、置信度或概率；
- [ ] 详情展示旧 payload 和旧版本且不调用 current；
- [ ] 旧请求不能覆盖新请求，关闭详情会释放状态；
- [ ] 页面无医疗诊断和自动调整计划入口；
- [ ] 所有测试数据、截图和示例均为虚构内容；
- [ ] 未新增迁移、未修改规则 YAML、哈希和快照表。

重点代码路径：

- `server/services/runner_state_snapshot_service.py`：范围、窗口查询与批量 JSON 字段读取；
- `server/api/routes/runner_state.py`：Timeline 路由顺序与鉴权上下文；
- `web/src/views/RunnerStateView.vue`：标签和保存；
- `web/src/components/runner-state/RunnerStateHistoryView.vue`：历史请求编排与竞态；
- `web/src/components/runner-state/RunnerStateVolumeChart.vue`：跑量与缺失值；
- `web/src/components/runner-state/RunnerStateTimeline.vue`：分类状态；
- `web/src/components/runner-state/RunnerStateSnapshotList.vue`：分页和同日记录；
- `web/src/components/runner-state/RunnerStateSnapshotDetail.vue`：不可变历史详情。
