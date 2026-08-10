# Weekly Facts 学习笔记

## Weekly Facts 不是自然语言周报

Weekly Facts 回答“数据库里能确定什么”；自然语言复盘回答“怎样向用户解释”。
前者由纯函数、枚举和版本化阈值生成，后者未来可以消费这些事实，但不得反过来
覆盖它们。这样即使 Provider 不可用，完成率、偏差和风险边界仍然成立。

## 为什么先算事实再让 LLM 解释

模型擅长语言组织，不适合作为公里、次数、关联和权限的权威来源。先由
`WeeklyFactsService` 查询当前用户，再由 `build_weekly_facts` 生成稳定对象，
未来 Agent 只能读取结果，可以避免幻觉数值、跨用户读取和模型改变训练规则。

## 计划完成率

次数完成率只统计“已完成且匹配到计划”的跑步课。距离完成率使用有效实际跑量
除以计划跑量；分母为零返回空值。缺失距离不会被当作一次零公里训练。取消计划
不进入分母，周内未来计划也不进入分母。

## 关键课不能被总跑量掩盖

某周可以通过额外轻松跑达到总公里数，却漏掉间歇、节奏或长距离。系统因此单独
计算关键课和长距离完成率，并产生 `KEY_SESSION_MISSED` 或
`LONG_RUN_MISSED`，避免“公里数相等”掩盖训练结构变化。

## 计划与日志匹配

1. 优先显式 `planned_workout_id`。
2. 没有关联时，尝试同日和规范化主类型唯一匹配。
3. 多候选时不猜，记录 `DUPLICATE_OR_AMBIGUOUS_LOG`。
4. 无候选时记录 `UNMATCHED_LOG`，已完成训练再记录 `EXTRA_SESSION`。
5. 相同活动指纹只统计一次。

跨午夜训练只有在现有日志已经提供业务 `activity_date` 或显式计划关联时才能
可靠归属；A 阶段不根据 UTC 时间戳猜自然日。

## 数据不足必须显式表达

`null`、`UNKNOWN` 和 `INSUFFICIENT_DATA` 是合法产品结果，不是服务器错误。
如果偷偷补零，用户会把“没有记录”误读为“确实没有训练”；如果根据一条状态
快照推趋势，结果也不可追溯。

## 确定性规则的优缺点

优点是可测试、可审计、相同输入结果一致、Provider 故障不影响。缺点是阈值需要
产品验证，难以覆盖所有训练语境。因此规则版本和 facts 版本都进入结果与哈希；
未来修改必须新增测试并说明兼容性，而不是在代码里散落魔法数字。

## 如何增加规则

1. 在 `enums.py` 增加有限状态或偏差类型。
2. 在 `rules.py` 集中声明阈值和类型集合。
3. 在 `aggregation.py` 用纯逻辑产生证据码。
4. 在固定虚构案例集中增加正例、边界值和反例。
5. 验证稳定哈希改变且旧规则不退化。
6. 更新规则与数据质量文档。

## 代码和验收路径

- Schema：`planner_core/weekly_review/schemas.py`
- 规则：`planner_core/weekly_review/rules.py`
- 聚合：`planner_core/weekly_review/aggregation.py`
- ORM 适配：`server/services/weekly_facts_service.py`
- 固定案例：`evaluation/weekly_review/cases_v1.json`
- 测试：`tests/test_weekly_facts_domain.py`

验收时重点检查跨用户过滤、未来日期、缺失值、关键课、重复匹配、Runner State
不足、同输入哈希稳定，以及服务中不存在 commit/flush/add/delete。

## 面试表达

可以概括为：“我把旧周报里混合的 SQL、统计和 LLM 拆成只读适配层与纯领域层。
服务端先生成版本化 Weekly Facts，明确匹配、缺失、数据质量和偏差，再允许未来
Agent 做解释。这样既能测试 30 多个固定案例，也能保证 Provider 故障时核心事实
不变，并通过用户过滤和无写事务维持数据边界。”
