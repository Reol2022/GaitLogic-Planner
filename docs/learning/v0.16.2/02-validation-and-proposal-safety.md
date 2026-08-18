# v0.16.2：验证与计划修改安全

部分事实只扩大“可以解释哪些已有事实”，不扩大“可以写入什么”。

Coach TODAY 的权威字段仍由服务端的确定性评估产生；模型只能解释，Validator 继续校验决策、计划状态、数据质量、风险提示和 Evidence。某领域 BLOCKED 时，模型不能把它描述为已知事实。

Weekly Review 即使为 `PARTIAL`，也不会自动变成 Plan Adjustment Proposal 可写。Proposal 服务仍验证用户归属、目标计划版本、已锁定/已完成状态、疲劳、训练量上限和连续高强度边界。恢复领域 BLOCKED 时，任何增加距离或强度的候选变化会被拒绝；减少或保持原计划仍由既有规则逐项验证。

测试重点：

- `tests/test_decision_readiness.py` 覆盖分类、软限制不全局阻塞和无训练事实的硬阻塞。
- `tests/test_agent_today_recommendation_validator.py` 覆盖 TODAY 的确定性字段与安全限制。
- `tests/test_adaptive_plan_proposal_service.py` 覆盖 Proposal 的既有边界。
- `web/src/components/weekly-review/WeeklyFactsPanel.test.ts` 覆盖 READY、PARTIAL、BLOCKED 的同屏显示。
