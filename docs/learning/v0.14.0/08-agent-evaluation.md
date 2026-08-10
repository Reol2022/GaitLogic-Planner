# Agent Evaluation

GaitLogic 的公开评测不是另一套业务逻辑，而是对现有 Coach、RAG、Retrieval 和 Weekly Adaptive runner 的统一编排。入口是 `scripts/evaluate_agent.py`，默认只运行离线、可复现、完全虚构的数据集，不读取竞赛私有案例，也不调用真实 Provider。

四个 suite 分别复用：`server.agent.evaluation` 的 Coach 32 例、`server.knowledge_retrieval.evaluation` 的 RAG 36 例与 Retrieval 60 例、以及 `server.weekly_review_evaluation` 的 Weekly Adaptive 32 例。统一层只把已有结果转换为安全的 `EvaluationRun`、`EvaluationSuiteResult`、指标、门禁和失败分类；它不复制 case，也不更改原有 metric 定义。

运行 `python scripts/evaluate_agent.py --suite all` 会把临时 JSON 和 Markdown 写到 Git 忽略的 `var/evaluations/`。历史基线在 `docs/evaluation/baselines/agent-regression-v1.json`，只可经人工审阅创建新版本，运行不会改写它。
