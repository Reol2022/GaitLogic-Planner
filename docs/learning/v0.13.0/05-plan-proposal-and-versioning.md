# Plan Proposal 与 Versioning

## 1. Proposal 解决什么

`planner_core/adaptive_plan/schemas.py::PlanAdjustmentProposal` 把修改建议表示成可审查 Diff。每个 `PlanAdjustmentChange` 包含 date、plan_id、base_plan_version、before、after、reason 和 rule_evidence，用户看到的不是一句“AI 建议调整”。

## 2. 规则边界

`AdaptivePlanProposalService.create_proposal()` 是纯领域服务，不打开事务。它拒绝跨用户目标、重复 plan_id、锁定或已完成计划、数据不足或冲突、高疲劳下增量/增强、超过既有周增幅边界，以及连续高强度日。

## 3. 应用与版本

`AdaptivePlanApprovalService.approve()` 把通过校验的 after 写入 `PlannedWorkout`，同时创建 `AdaptivePlanVersionRecord`。版本保存 previous/new snapshot、proposal、actor、source 和原因。数据库模型在 `planner_core/database/models.py`，建表和回滚脚本在 `scripts/upgrade_v0130_adaptive_plan.py`，基线 DDL 同步到 `sql/schema.sql`。

```text
version N plan
    |
    +-- proposal P (before N, after N+1)
    |
human approve
    |
transaction: update plan + insert version N+1
    |
rollback request
    |
transaction: restore snapshot + insert version N+2
```

## 4. 为什么回滚也创建版本

物理删除历史会破坏审计，也无法回答“谁在什么时候恢复了哪个状态”。回滚是新的业务动作，因此恢复旧快照后生成新版本；旧 Proposal 和旧版本均保留。

## 5. MySQL 兼容

脚本使用项目既有 SQLAlchemy/MySQL 方式，包含 upgrade 和 downgrade。唯一约束与索引负责 proposal/version/checkpoint 查询。MySQL 5.7 与 8 必须在隔离数据库验证；没有凭据或建库权限时测试只能明确 skip，不能宣称通过。

## 6. 测试

`tests/test_adaptive_plan_proposal_service.py` 测纯规则；`tests/test_adaptive_plan_hitl.py` 测数据库事务、幂等、权限、版本和回滚；`tests/test_adaptive_plan_api_structure.py` 测公共方法只有受控 GET/POST，没有任意 PUT/PATCH/DELETE。

## 7. 常见错误

不要只保存 after 而丢失 before；不要用客户端传来的 base version；不要在提交事务之后才检查规则；不要用更新旧版本记录的方式实现回滚；不要把 Proposal 状态当成数据库唯一幂等手段而忽略并发锁。

## 8. 面试回答

30 秒回答：Proposal 是无副作用的结构化 Diff，规则服务先限定候选边界；批准时服务端在行锁事务内重验所有权、锁定与 base version，再更新计划并写不可变审计版本。重复批准返回原版本，回滚创建新版本而不是删历史。
