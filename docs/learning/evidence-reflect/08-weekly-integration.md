# Weekly Integration

Weekly Graph 当前顺序为：

```text
load_weekly_facts
 -> assess_weekly_evidence
 -> reflect_weekly_evidence
 -> evaluate_weekly_rules
 -> RAG
 -> Weekly analysis
 -> Validator
 -> Plan design / fallback
```

Weekly Reflect 只调用 WEEKLY_REVIEW 允许的现有系统工具，不暂停等待用户填写 RPE。无法补齐的 subjective fatigue 保持 MISSING/BLOCKED，但其他 domain 仍可生成周复盘。

Evidence 补充与 Proposal Safety 分离。Plan Designer 会看到 evidence/readiness；最终 Proposal 仍由 `AdaptivePlanProposalService` 独立校验，BLOCKED recovery 不能支持负荷或强度增加。
