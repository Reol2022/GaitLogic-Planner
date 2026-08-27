# Decision Relevance

Evidence Judge 只评估当前问题需要的 domain。`relevant_domains_for_request()` 对正式 Intent 使用固定 profile；GENERAL 问题再用小型确定性分类：跑量问题只需要 `training_volume`，恢复问题需要 `recovery` 与 `subjective_fatigue`，强度问题需要 `recent_intensity / training_load / recovery`。

因此“最近一周跑了多少”不会因为 RPE 缺失触发恢复工具。Required Evidence Profile 是 typed code mapping，不散落在 Prompt 中，也没有引入可执行数据库表达式。
