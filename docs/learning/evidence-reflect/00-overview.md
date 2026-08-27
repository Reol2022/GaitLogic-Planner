# Evidence Judge + Reflect 概览

本能力不是 Multi-Agent。它是在现有 Coach 与 Weekly 工作流中增加两个确定性阶段：Evidence Judge 判断当前任务相关决策域的证据是否存在、可用、完整或冲突；Reflect 根据缺口从现有只读 Tool Registry 中选择可补充的数据源。

```text
Initial facts/tools
  -> Evidence Judge
  -> Decision Readiness
  -> bounded Reflect (0..1 by default)
  -> targeted existing read tool
  -> Evidence rejudge
  -> LLM explanation
  -> Validator
```

默认 `EVIDENCE_MAX_REFLECT_ROUNDS=1`，允许范围为 0–2。Evidence Judge 不生成训练规则、不修改计划，也不使用 RAG 推测个人状态。核心实现位于 `server/domain/evidence.py`、`server/services/evidence_judge_service.py` 和 `server/services/evidence_reflect_service.py`。
