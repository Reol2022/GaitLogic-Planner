# Coach Agent Evaluation v1 学习说明

## 为什么不能只看“接口返回 200”

Agent 可能调用错工具、丢失 Warning、覆盖确定性 Decision，或者在 Provider 失败时没有安全降级。Evaluation 把这些产品契约变成逐案例断言。

## 为什么不用另一个 LLM 当裁判

第二个模型会引入不可重复性、成本和新的偏差。v1 只判断明确结构：Intent、工具、状态、Decision、Warning、Limitation 和有限的禁止声明。

## 如何新增 Fixture

在 `server/agent/evaluation/fixtures.py` 注册固定、虚构的 Tool 输出。所有输出必须通过正式 Tool Output Schema。不要复制真实用户记录，也不要依赖运行当天日期。

## 如何新增案例

在 `evaluation/coach_agent/cases_v1.jsonl` 增加一行，并确保：

1. `case_id` 唯一；
2. Intent 当前公开；
3. Fixture 已注册；
4. 工具来自正式八工具集合；
5. 今日案例声明 Decision 和 Planned Status；
6. 禁止声明是可确定性检查的短语。

运行 Loader 测试确认 Schema。

## Context Tool 与 Model Tool

Context Builder 会按 Intent 预加载事实；模型也可能主动请求 Tool。Trace 使用不同 Event Type，Reporter 分开保存两类工具，Required Tool Recall 不把两者混淆。

## 如何增加断言

结构断言放在 `assertions.py`，聚合指标放在 `metrics.py`。新增断言必须：

- 可重复；
- 不读取敏感内容；
- 不依赖模型主观评分；
- 有正向和失败测试；
- 明确适用分母。

## 如何解释满分

满分表示当前 32 条虚构案例全部满足已编码契约，不表示模型“聪明”、训练建议具有医学效力或真实 Provider 永不失败。案例集、Prompt 和 Git Commit 会写入报告以限制结论范围。

## CLI 调试

```powershell
python scripts/evaluate_coach_agent.py --case-id today_002 --no-write
```

退出码 1 表示断言失败，2 表示输入或筛选错误。报告不会打印完整 Context 或 Provider 内容。

## 项目负责人验收清单

- [ ] 32 条案例全部加载；
- [ ] 分类数量符合设计；
- [ ] 固定日期和 Asia/Shanghai；
- [ ] 无网络、真实 Provider 或生产数据库；
- [ ] Context/Model Tool 分离；
- [ ] Decision、Plan、Warning、Limitation 指标存在；
- [ ] 失败案例能进入报告；
- [ ] JSON 不含 Prompt、Context、用户身份或工具完整结果；
- [ ] CLI 退出码有测试；
- [ ] 报告中的百分比来自本次真实运行。
