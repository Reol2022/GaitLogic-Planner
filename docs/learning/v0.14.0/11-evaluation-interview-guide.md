# Evaluation Interview Guide

## 为什么 Agent 不能只做单元测试？

Agent 的风险常发生在多个组件交界处：Tool 被错误选择、检索引用错源、模型措辞覆盖规则，或 Fallback 丢失警告。单元测试很难替代固定案例下的端到端行为比较，因此 GaitLogic 同时维护 pytest 和公开评测。

## Baseline 为什么不能自动更新？

自动更新会把“退化”改写为“新正常”。本项目把 baseline 放在版本化 JSON 中，只有人工确认后才新增新版本；执行评测仅写 Git 忽略的临时报告。

## Safety Metric 和 Quality Metric 的差别？

Safety Metric 有清晰业务边界，例如未授权写入、规则违规和来源幻觉必须为零，Warning Retention 必须为 100%。Quality Metric 如 Recall@4、MRR@4、nDCG@4 用来监测质量变化，不能武断要求 100%。

## Provider Failure 为什么单独分类？

Provider 或环境故障不是产品规则退化。统一结果使用 `PROVIDER_FAILURE` 与 `ENVIRONMENT_BLOCKER`，避免把网络、配置、索引损坏和业务规则错误混为一句“case failed”。默认 suite 离线运行，真实 Provider Smoke 仍走专用命令。

## Trace 和 Evaluation 如何配合？

两者独立：Evaluation 负责可重复的质量判定，Trace 负责一次请求的运行时路径。以后可把安全的 `evaluation_run_id` 放进 Trace metadata，以 case ID 关联 Tool、RAG、Validator 的延迟；不会记录问题正文、Prompt 或模型原文。
