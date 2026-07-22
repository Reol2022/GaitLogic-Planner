# GaitLogic Coach Agent Foundation v1 实现说明

## 实现概览

v0.11.0-A 在 `server/agent` 中新增纯内部 Agent Core。当前实现没有路由、数据库表或真实模型适配器。调用方必须注入 Gateway，并在调用前准备安全的领域上下文。

## 实际执行过程

1. 创建 `AgentRequest`，其中用户引用必须来自服务端认证上下文。
2. `AgentResponseValidator` 拒绝未知意图和超限请求。
3. `AgentContextBuilder` 把安全 Pydantic/Mapping 数据转换为有界 JSON。
4. 注册表按意图向 Gateway 暴露只读工具定义。
5. Gateway 返回结构化 `AgentModelOutput`。
6. 若没有工具调用，校验后直接返回。
7. 若有工具调用，注册表逐个执行并校验输入输出。
8. 工具结果进入上下文后，只允许第二次 Gateway 调用。
9. 最终校验成功后返回 `AgentResponse`；失败只返回稳定错误码和安全文案。

## 如何注册工具

定义 Pydantic 输入/输出模型，继承 `AgentTool`，声明名称、说明、允许意图与只读属性，再由产品组合层显式调用 `AgentToolRegistry.register`。注册表不接受裸函数、动态模块路径或用户代码。当前仓库只在测试中注册虚构工具，尚未注册真实训练工具。

## 如何实现 Gateway

Provider 适配器应实现 `AgentLLMGateway.generate`，并把厂商响应转换为 `AgentModelOutput`。网络、重试、密钥与模型配置只能留在适配器边界；编排器、Schema、Trace 和工具不得依赖具体厂商。v0.11.0-A 仅提供无网络 Mock。

## Validator 与 Trace

Validator 在模型调用之外以确定性规则验证意图、工具、风险、数据限制和敏感输出；它不会再调用模型。Trace 记录请求校验、Context、模型、工具、最终校验和结束事件，只保留 UUID、状态、安全错误码与耗时。

## 错误码

公开安全码包括：`AGENT_INVALID_REQUEST`、`AGENT_UNKNOWN_INTENT`、`AGENT_TOOL_NOT_FOUND`、`AGENT_TOOL_NOT_ALLOWED`、`AGENT_TOOL_ARGUMENTS_INVALID`、`AGENT_TOOL_EXECUTION_FAILED`、`AGENT_MODEL_OUTPUT_INVALID`、`AGENT_MODEL_FAILED`、`AGENT_VALIDATION_FAILED`、`AGENT_CALL_LIMIT_EXCEEDED` 和 `AGENT_INTERNAL_ERROR`。响应不返回 Python 异常正文。

## 配置

内部安全上限沿用项目 `Settings`：

- `AGENT_MAX_MODEL_CALLS=2`
- `AGENT_MAX_TOOL_CALLS=6`
- `AGENT_MAX_SAME_TOOL_CALLS=2`
- `AGENT_MAX_MESSAGE_LENGTH=4000`
- `AGENT_MAX_CONTEXT_ITEMS=50`
- `AGENT_MAX_ANSWER_LENGTH=6000`

配置不包含 Provider、模型、温度或 API Key。`AGENT_MAX_MODEL_CALLS` 不能超过 2。

## Mock 使用示例

以下数据完全虚构：

```python
request = AgentRequest.for_authenticated_user(
    user_id=9001,
    message="请解释我当前训练状态中的数据不足。",
    intent=AgentIntent.EXPLAIN_RUNNER_STATE,
)
gateway = MockAgentLLMGateway(
    AgentModelOutput(
        intent=AgentIntent.EXPLAIN_RUNNER_STATE,
        answer="目前可用数据不足，因此只能解释已提供的指标。",
        risk_level=AgentRiskLevel.UNKNOWN,
        limitations=[
            AgentNotice(code="DATA_LIMITED", message="当前有效训练记录较少。")
        ],
    )
)
response = GaitLogicCoachAgent(gateway=gateway).run(request)
```

这个示例不会访问网络、数据库或 Garmin。

## 与既有能力的关系

Runner State、推断规则、状态快照、训练日志、计划完成率和 Weekly Review 仍由现有产品服务负责。Agent Context 只接收它们已授权、已聚合的输出。Agent 不复制查询和计算公式。

现有 AI 课表草稿功能未迁移到 Agent Gateway，也未被修改。

## 当前限制

- 没有公共 API 或页面。
- 没有真实 Provider Gateway。
- 没有长期记忆和 Trace 持久化。
- 没有产品工具默认注册。
- 没有计划生成、计划修改或动态调整。
- 没有 Garmin 自动触发。
- 不提供医学诊断。

## 开源边界

可公开：契约、编排器、Mock、确定性校验器、错误码、虚构测试和技术文档。

不得公开：真实用户上下文、真实 Agent 对话、真实工具调用结果、API Key、Garmin Token、数据库凭据、竞赛实验数据、真实 Prompt 调优记录。
