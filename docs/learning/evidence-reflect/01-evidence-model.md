# Evidence Model

`EvidenceItem` 区分五类来源语义：

- `PERSONAL_FACT`：计划、日志、RPE、用户输入和规范化设备事实。
- `DERIVED_FACT`：由可回溯输入计算出的跑量、频率和负荷。
- `RULE_DECISION`：规则引擎已经生成的确定性结论。
- `KNOWLEDGE_EVIDENCE`：RAG 知识，只支持原理解释。
- `CAPABILITY_INFORMATION`：系统尚不支持或阈值未定义等能力边界。

证据带有 canonical fact identity、来源、时间窗口、freshness、coverage、usability 和 limitation codes。系统不生成无法解释的浮点“模型置信度”。`EvidenceAssessment` 的状态为 `SUFFICIENT / PARTIAL / CONFLICTED / MISSING / NOT_APPLICABLE`，再单向映射为已有 `DecisionReadiness`。
