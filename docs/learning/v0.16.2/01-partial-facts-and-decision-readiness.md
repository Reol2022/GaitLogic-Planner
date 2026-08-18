# v0.16.2：部分事实与决策准备度

## 问题

旧链路把 RPE 缺失、训练阶段未结构化、复合课强度估计和暂未启用的规则能力都放在同一个 `limitations` 列表中。调用方只要看到列表非空，就容易把整次 TODAY 或 Weekly Review 表示为“数据不足”。这会丢掉已经可靠的跑量、频率、计划执行和 Runner State 事实。

## 统一语义

`LimitationClass` 位于 `server/domain/decision_readiness.py`：

- `HARD_BLOCKER`：当前决策所需的核心事实不可用，例如所有 TODAY 核心来源均不可用。
- `SOFT_LIMITATION`：某个分析维度范围受限，例如 RPE、心率、训练阶段或结构化分段不足。
- `CAPABILITY_LIMITATION`：系统当前没有实现某条规则，不能被解释为用户身体或训练数据异常。

`DecisionReadiness` 也在同一模块中：

- `READY`：该领域的确定性事实可支持结论。
- `PARTIAL`：可得出受限结论，但必须携带限制。
- `BLOCKED`：该领域不能产生确定性结论。
- `NOT_APPLICABLE`：该领域当前不适用，不等于数据缺失。

总体准备度不是“所有领域都 READY”的布尔值。只要仍有有意义的 `READY` 或 `PARTIAL` 领域，就可以为整体生成受限分析；只有没有任何可用领域时，整体才是 `BLOCKED`。

## 实现位置

- Runner State 在 `server/services/runner_state_inference_service.py` 生成领域准备度，并保留旧 `limitations` 以保持 API 兼容。
- TODAY 在 `server/agent/today_recommendation.py` 仅在三个核心训练事实来源同时缺失时附加 `TODAY_CONTEXT_INCOMPLETE`。
- Weekly Facts 在 `planner_core/weekly_review/aggregation.py` 逐领域输出准备度，避免“没有计划”掩盖已经存在的训练日志。
- Proposal 在 `server/services/adaptive_plan_proposal_service.py` 仍单独保护写入：恢复领域 BLOCKED 时，不能依据它提高训练负荷或强度。
- 前端 Weekly Facts 面板展示每个领域的准备度；Coach 提示把软限制、能力限制和数据不足分别呈现。

## 前后对比

| 情况 | 旧的误导性表现 | v0.16.2 表现 |
| --- | --- | --- |
| RPE 缺失 | 整体数据不足 | 训练负荷仍 READY，主观疲劳 BLOCKED |
| 训练阶段缺失 | 整体数据不足 | 训练阶段 BLOCKED，其他领域继续分析 |
| Garmin 恢复字段部分缺失 | 整体数据不足 | 恢复 PARTIAL，训练事实可继续使用 |

这不会让 TODAY 的确定性规则跨越真正缺失的必需事实，也不会放宽计划修改的事务、HITL、版本或规则校验边界。
