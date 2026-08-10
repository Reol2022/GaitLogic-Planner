# Adaptive HITL and Plan Versioning v1

Phase D 使用 LangGraph `interrupt` 暂停审批流，并通过 SQLAlchemy/MySQL checkpointer 保存
checkpoint 和 pending writes。`thread_id` 是恢复游标；服务重启后仍可用 `Command(resume=...)`
继续，而生产设计不依赖内存状态。

Proposal 使用现有 `training_adjustment_drafts` 持久化。正式写入只发生在认证用户调用 approve、
服务端重新核对归属、基础 `plan_version`、锁定/完成状态后，并在同一事务中更新计划与写入
`adaptive_plan_versions` 审计快照。重复 approve 只返回已有版本，不重复写入；reject 不修改计划。

回滚不会删除历史版本，而是根据 before snapshot 恢复业务字段、递增当前计划版本，并新增一条
`controlled_rollback` 审计记录。数据库变更由 `scripts/upgrade_v0130_adaptive_plan.py` 提供完整
upgrade/downgrade；生产执行前仍需备份并在隔离 MySQL 5.7/8 环境验证。
