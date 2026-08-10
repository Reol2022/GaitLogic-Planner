# Regression Testing

单元测试回答“这段代码在给定输入下是否符合契约”；Evaluation 回答“一个完整 Agent 行为在一组代表性虚构案例中是否发生退化”。两者互补：pytest 覆盖小的边界和异常路径，统一评测覆盖 Tool、规则、检索、Fallback 以及周复盘的结果链路。

Regression 的参照物是版本化 baseline，而不是临时运行的最好成绩。`EvaluationBaselineManifest` 保存公开数据集版本与度量值；当前运行只计算 current、baseline、delta 和 Gate，绝不自动覆盖 baseline。这样更换模型、修改 Retriever 或改动编排后，结果下降能被看见，而不是被脚本“更新”为新标准。

安全门禁与质量门禁不同。规则违规、来源幻觉、未授权写入等具有明确的零容忍边界；Recall@4、MRR@4、nDCG@4 等质量指标与既有 baseline 比较。当前 Retrieval baseline 中已有的非零 `forbidden_document_rate` 被透明保留为历史质量问题，不能通过修改基线或伪称 0 来掩盖。
