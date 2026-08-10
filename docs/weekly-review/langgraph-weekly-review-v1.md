# LangGraph Weekly Review v1

该工作流是 v0.13 的独立周复盘编排，不改写 v0.12 Coach Agent。它使用
`langgraph==1.2.9` 的 `StateGraph`、命名节点、普通边和条件边，把确定性
Weekly Facts、规则结果、训练知识引用、模型叙事、验证和回退串成一条可测试链路。

流程为：

`load_weekly_facts -> evaluate_weekly_rules -> retrieve_training_knowledge -> generate_weekly_review -> validate_weekly_review -> finalize_weekly_review`

验证失败时条件边进入 `fallback_weekly_review`，然后仍由服务端完成最终装配。
模型只能生成叙事字段和请求内知识引用 ID；Weekly Facts、规则、警告、限制和公开
知识引用均由服务端保留或还原。RAG 禁用、Embedding 失败或 Chat Provider 失败不会
改变事实层，也不会获得计划写权限。

Phase B 暂不使用 checkpointer 或 interrupt；这些能力只在 Phase D 的人工审批中启用。
