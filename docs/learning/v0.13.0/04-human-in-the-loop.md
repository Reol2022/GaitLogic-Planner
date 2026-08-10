# Human-in-the-loop

## 1. 目标

HITL 解决的是授权问题，不是让用户替模型补数据。模型和规则只能形成 Proposal；只有认证用户明确批准，服务端重新校验后才允许修改计划。

```text
Proposal
  -> request_human_approval()
  -> interrupt(payload)
  -> SQLAlchemy checkpoint
  -> API returns pending proposal
  -> user approve/reject
  -> Command(resume=decision)
  -> ownership + stale version + rule validation
  -> transaction
  -> new plan version
```

## 2. 真实代码

图定义在 `server/adaptive_workflow/graph.py`。`AdaptiveApprovalState` 是最小状态，`request_human_approval()` 只暴露安全审批载荷。持久化由 `server/adaptive_workflow/checkpointer.py` 完成。真正写入位于 `server/services/adaptive_plan_approval_service.py::approve()`，拒绝位于 `reject()`。

## 3. 为什么 LLM 没有写工具

通用 `update_training_plan` 会把模型输出直接转成数据库权限，难以保证用户归属、锁定状态、计划版本和训练规则同时成立。当前设计让模型输出无副作用结构；API 从 JWT 注入用户；服务端持行锁、检查原版本和规则，再提交事务。

## 4. 并发与幂等

批准时锁定 Proposal 记录和目标计划。Proposal 已应用则返回已有版本，不再重复改课；基础计划版本不一致则判定 stale；事务异常统一回滚。因此“双击确认”和两个并发请求不能形成两次业务写入。

## 5. Reject 与 Edit

v0.13 已实现 approve/reject。Reject 只改变提案状态，不写训练计划。通用 Edit 未开放，因为编辑后的候选仍需完整规则重验；未来若增加，应创建新候选或修订记录，而不是直接改已审批内容。

## 6. 测试

`tests/test_adaptive_plan_hitl.py` 覆盖未登录、跨用户、拒绝零计划写入、批准一次、重复批准、规则失败、事务回滚、checkpoint 恢复和版本回滚。API 契约由 `tests/test_adaptive_plan_api_structure.py` 验证不接收 user_id。

## 7. 常见错误

把“用户点击按钮”当成唯一安全检查是不够的；前端可伪造请求。还必须在事务内重新查询当前用户资源并验证版本。另一个错误是把内存 checkpointer 当生产恢复方案，进程重启后审批会丢失。

## 8. 面试回答

30 秒回答：审批是安全边界。Graph 用 interrupt 暂停并持久化状态，用户从受保护 API 批准后通过 Command 恢复；写服务再次做所有权、版本、锁定和规则校验，最后原子更新并生成审计版本。LLM 从未获得数据库写权限。
