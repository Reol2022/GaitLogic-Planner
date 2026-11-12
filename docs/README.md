# GaitLogic 文档中心

[项目首页](../README.md) · [English](../README-EN.md) · [更新历史](更新历史.md)

README 介绍产品定位、核心能力与使用入口；本目录保存设计、部署、验收和版本记录。各报告的版本、日期和验收状态以报告自身标记为准，历史方案不代表当前线上实现。

## 使用与系统介绍

- [系统界面与功能介绍](../README.md#-系统介绍)
- [快速开始](../README.md#-快速开始)
- [数据库设计](../md/数据库设计.md)
- [Excel 字段映射](../md/Excel字段映射.md)
- [后端学习指南](../md/BACKEND_LEARNING_GUIDE.md)

## 训练事实与风险边界

- [Runner State 数据模型](training-knowledge/runner-state-model-v1.md)
- [Runner State 推断规则](training-knowledge/runner-state-inference-v1.md)
- [每周训练事实模型](weekly-review/weekly-facts-domain-v1.md)
- [每周训练数据质量](weekly-review/weekly-facts-data-quality-v1.md)
- [训练知识引用界面与边界](rag/training-knowledge-reference-ui-v1.md)

## Coach、MCP 与评测

- [Garmin Smart Sync：架构、迁移与运行](deployment/garmin-smart-sync.md)

- [Coach 架构](agent/coach-agent-architecture-v1.md)
- [Coach 示例与启动](agent/coach-agent-demo-v1.md)
- [MCP 集成与验收报告](evaluation/mcp-remote-e2e-report.md)
- [知识检索 Holdout 报告](evaluation/reports/retrieval-holdout-v2.md)
- [学习与架构资料索引](learning/README.md)

## 开发与部署

- [管理控制台](development/admin-console-mvp.md)
- [AI Plan 个性化上下文](development/ai-plan-personalization-v2.md)
- [Gilo 教练对话体验](development/gilo-chat-experience.md)
- [部署说明](DEPLOYMENT.md)
- [重新部署脚本说明](REDEPLOY.md)
- [Remote MCP 部署与回滚](deployment/mcp-production-rollout.md)

## 版本记录

- [更新历史](更新历史.md)：新增、改进、修复和兼容性变化。
- [发布说明目录](release/)：对应版本的发布范围与边界。
- [开发验收目录](development/)：实现说明、测试证据及未解决事项。
