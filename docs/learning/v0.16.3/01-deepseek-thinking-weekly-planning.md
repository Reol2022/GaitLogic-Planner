# DeepSeek Thinking、工具多轮与周复盘规划拆分

## 1. DeepSeek Thinking 是什么

Thinking 模式会先在 Provider 的 `reasoning_content` 中进行内部推理，再在 `content` 中给出最终正文。两者共享 Provider 的输出预算，因此只看最终正文长度无法判断 Token 是否足够。`finish_reason=length` 且正文为空、reasoning 非空，表示预算在最终正文形成前已经耗尽。

## 2. Agent Loop 为什么保留 reasoning_content

DeepSeek Thinking 与原生 Tool Calling 组合时，下一轮必须收到上一轮完整 assistant turn，包括 `reasoning_content`、`content`、`tool_calls` 和原始 Provider tool-call ID。只重建业务 Context 或只回放工具名称，会破坏 Provider 的多轮协议。

GaitLogic 使用 `AgentExecutionState` 保存这条原生消息链。工具执行结果按原始 `tool_call_id` 追加，随后再调用下一轮模型。

## 3. request-local messages 存在哪里

消息链只存在当前 Python HTTP 请求调用栈中的 `AgentExecutionState`：请求开始时创建，Agent 完成或降级后随局部变量释放。普通 Coach 请求不写 Redis、文件或数据库。

这是一条用户请求内部的多轮 Provider/Tool interaction，不是跨多个用户消息的 Conversation Memory。现有显式 `conversation_context` 仍是独立、受限的产品输入。

## 4. 为什么 Coach Reasoning 不持久化

Coach 调用频繁，raw reasoning 体积大、不可验证，也不是训练业务事实。它只为同一请求内的 Tool Calling 协议服务。请求结束后释放可以降低隐私、存储和错误依赖风险。

## 5. 为什么 Weekly 与 Plan Reasoning 可选保存

周复盘与计划设计属于低频、高价值、模型升级敏感任务。内部 `provider_reasoning_records` 可以在配置开启时保存 raw reasoning、Token 数值、模型和 finish reason，用于诊断。它不进入 REST、MCP、Trace、Metrics、Evaluation、RAG、规则或 Validator。

Reasoning 记录通过用户外键隔离；删除用户时级联删除。它没有公开读取 API，部署方可以另行制定内部保留周期。

## 6. Weekly Review 和 Plan Design 为什么拆为两个请求

复盘回答“本周发生了什么、哪些结论受事实支持”；计划设计回答“在现有下周计划和安全约束内应怎样调整”。两者都需要 Thinking，但上下文、Schema、Token、重试和 finish reason 独立。

第一阶段只传递经过 Pydantic 校验的 `WeeklyReviewAnalysis`，不会把上万字 raw reasoning 放进第二次请求。这样既避免上下文膨胀，也避免 Plan Design 把不可验证思维过程当作 canonical evidence。

## 7. Structured Materialize

`PlanDesignAnalysis` 只产生候选调整。`DeterministicProposalMaterializer` 使用 Python、Pydantic 和现有 `AdaptivePlanProposalService` 生成 `PlanAdjustmentProposal`。本轮没有第三次 LLM。

Materialize 之后仍执行用户归属、Partial Facts、恢复域阻断、负荷和强度边界、连续高强度日、基础版本、行锁、HITL、事务和新版本记录。更强的模型推理不会降低写入安全边界。

## 8. reasoning_content 不能成为业务事实

Raw reasoning 可能包含未验证推断、被废弃的候选思路和 Provider 私有格式。业务依赖只能是结构化中间表示、确定性规则、Canonical Weekly Facts 和最终 Proposal。Reasoning 只是一种内部诊断材料。

## 9. finish_reason=length 不是 JSON Error

Provider 响应检查顺序是：Transport → finish reason → 空正文 → JSON → Pydantic Schema → 业务校验。长度截断必须先归类为 `PROVIDER_OUTPUT_TRUNCATED`；reasoning-only exhaustion 通过安全的 reasoning/content 长度诊断，不能落入 `json.loads("")`。

## 10. Task Model Profile 与 Token Budget

任务 Profile 区分 Coach Fact、Coach Analysis、Weekly Review Analysis、Plan Design 和 AI Plan Generation。每类任务单独配置模型、Thinking、最大输出 Token、结构化格式和有限重试。

Token Budget 按任务复杂度和真实 Provider 行为设置，而不是按“几周计划”推断。截断重试最多按受控倍率提高预算，且总次数和 65536 上限固定，禁止无限扩张。

## 11. Trace 如何诊断 reasoning token 问题

SafeTracer 仅允许记录 `task_type`、`model_profile`、Thinking 开关、工具轮次、finish reason、reasoning/content 长度、最大 Token、重试次数和失败分类。它禁止 Prompt、raw response、reasoning 文本、完整 Tool Result 和用户训练正文。

当 `finish_reason=length`、`content_length=0` 且 `reasoning_length>0` 时，Metrics 同时记录输出截断和 reasoning budget exhaustion 聚合计数，不使用 user ID、trace ID 或文本作为 label。
