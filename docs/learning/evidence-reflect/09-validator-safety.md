# Validator Safety

Agent Validator 与 Weekly Validator 都调用确定性的 `evidence_claim_violations()`：

- MISSING/BLOCKED domain 的确定性个人结论被拒绝。
- CONFLICTED domain 不能选择一方并输出绝对结论。
- PARTIAL domain 不能使用“可以确定、明确、一定”等确定性语言。

校验采用小型高风险短语表，不把它包装成概率模型。失败后沿用现有 Validator/Fallback 路径。RAG Canonical Reference、计划修改禁令、医学诊断禁令和 Today deterministic decision 校验保持独立。
