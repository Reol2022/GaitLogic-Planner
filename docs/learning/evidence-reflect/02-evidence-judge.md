# Evidence Judge

`EvidenceJudge.assess()` 只消费 canonical evidence，并按当前 relevant domains 评估：required fact 是否存在、类型是否允许、覆盖是否完整、数据是否过期、是否可用以及是否冲突。

`SUFFICIENT` 映射为 `READY`；`PARTIAL` 和 `CONFLICTED` 映射为 `PARTIAL`；`MISSING` 映射为 `BLOCKED`。这层不重算训练规则，也不覆盖 Weekly Classification 或 Today Evaluation。

稳定 evidence fingerprint 只包含可用 evidence identity、coverage、usability 和语义状态，用于判断补取前后是否产生边际增益。
