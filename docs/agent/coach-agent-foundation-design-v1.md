# GaitLogic Coach Agent Core Foundation 设计 v1

## 1. 目标

v0.11.0-A 只建立可测试、可替换、可审计的 Agent 内部基础设施。它把已有的 Runner State、训练统计和规则能力视为未来可注入的数据来源，不复制这些领域计算，也不提供公共 API、真实模型连接、持久化记忆或训练计划写入能力。

本阶段的核心数据流为：

```text
内部 AgentRequest
→ 确定性请求校验
→ 有界 AgentContext
→ Provider-neutral LLM Gateway
→ 显式只读 Tool Registry
→ 确定性响应校验
→ AgentResponse + 安全 Trace
```

这里的 Agent 是“受控编排器”，它能根据结构化上下文决定是否调用显式工具，再综合结果。普通 Chat Completion 只完成一次文本生成，并不自带工具权限、输入输出契约、调用上限、结果验证和 Trace。v0.11.0-A 也不是多 Agent 系统：不存在 Agent 间通信、委派或自治协作。

## 2. 设计边界

允许：结构化请求和响应、意图枚举、上下文装配、显式工具契约、Mock Gateway、确定性安全校验、内存 Trace、单元测试。

不允许：公开路由、数据库迁移、状态持久化、真实 LLM SDK 调用、Garmin 调用、训练计划生成或修改、医学诊断、自动动态调整、Agent 长期记忆。

## 3. 模块结构

- `server/agent/schemas.py`：严格 Pydantic 契约和调用上限。
- `server/agent/enums.py`：意图、运行状态、工具状态、风险等级和 Trace 枚举。
- `server/agent/context.py`：把调用方已取得的安全领域数据装配成 JSON-only 上下文。
- `server/agent/tool.py`：只能通过 `AgentTool` 子类声明显式工具。
- `server/agent/registry.py`：注册、按意图筛选、输入输出校验和安全失败转换。
- `server/agent/gateway.py`：Provider-neutral 抽象与无网络 Mock。
- `server/agent/validator.py`：确定性边界校验。
- `server/agent/orchestrator.py`：有界编排，不循环自主执行。
- `server/agent/trace.py`：只记录安全元数据的内存 Trace。

## 4. 意图

第一版支持：

- `TODAY_RECOMMENDATION`
- `WEEKLY_REVIEW`
- `EXPLAIN_RUNNER_STATE`
- `GENERAL_TRAINING_QUESTION`
- `UNKNOWN`

`UNKNOWN` 是拒绝态，不会触发 Gateway 或工具。

## 5. Agent Request 与身份边界

`AgentRequest.user_id` 只能由未来的认证服务端入口注入。当前没有公共 API，客户端也没有提交该结构的入口。请求包含服务端生成的 UUID、单条消息、显式意图和有界会话上下文。Pydantic 配置拒绝额外字段，限制消息条数、单条长度和总长度。

## 6. Agent Context

上下文包含内部用户引用、当前业务时区、会话上下文以及可选的 Runner State、近期训练、今日训练、当前周期、适用规则、数据质量和缺失原因。数据必须能转换为普通 JSON，不保留 ORM 实例、数据库 Session、Token、API Key 或原始 Provider payload。

`AgentContextBuilder` 不查询数据库。未来领域服务应先按当前用户完成权限查询，再把必要的安全 Schema 交给 Builder。这保证 A 阶段不会建立第二套 Runner State 或训练统计逻辑。

## 7. Tool 契约与注册表

工具必须是显式 `AgentTool` 子类，并声明：

- 稳定名称和说明；
- Pydantic 输入和输出类型；
- 只读属性；
- 是否需要确认；
- 允许调用的意图。

注册表拒绝任意函数和重名工具；向 Gateway 只暴露当前意图允许的工具。每次调用都会再次校验权限、输入和输出。异常不会把堆栈或原始异常文本返回给模型或用户。

v0.11.0-A 不注册任何产品写工具。

## 8. LLM Gateway

`AgentLLMGateway` 只定义结构化生成接口，不包含厂商、模型名称、温度、密钥或网络客户端。`MockAgentLLMGateway` 从预置结果队列返回确定性输出，可模拟异常并记录调用次数和工具暴露名称。

现有 AI 课表服务仍维持原有行为，不在本阶段迁移或改造。

## 9. 编排流程和调用上限

默认安全上限：

| 参数 | 默认值 |
| --- | ---: |
| 模型调用次数 | 2 |
| 单次运行工具总次数 | 6 |
| 同一工具次数 | 2 |
| 用户消息字符数 | 4000 |
| 上下文集合项数 | 50 |
| 最终回答字符数 | 6000 |

第一轮模型输出可以直接回答，也可以请求工具。需要工具时，编排器按顺序执行已验证的只读工具，将结果追加到结构化上下文，然后进行且仅进行第二次模型调用。第二轮仍请求工具会被拒绝。没有递归规划、开放循环或后台自主运行。

这些内部上限可通过现有 Settings 的 `AGENT_*` 环境变量配置，但 `max_model_calls` 的结构上限固定为 2。

当前限制采用确定性字符数和集合项数，而不是声称精确的模型 Token 计数；真实 Provider 接入阶段还需要在 Gateway 边界增加与具体 tokenizer 兼容的生产 Token 预算。

## 10. 确定性响应校验

校验器至少检查：意图一致、最终回答存在、长度、工具数量、工具是否存在、意图权限、只读属性、参数结构、敏感内容、医学诊断措辞、声称已经修改正式训练计划、高风险提示、低质量数据限制说明、工具结果引用和工具失败后的诚实降级。

校验器只做确定性边界校验，不生成运动科学结论，也不重新计算 Runner State。

## 11. 错误与状态

运行状态为 `SUCCEEDED`、`VALIDATION_FAILED`、`TOOL_FAILED`、`MODEL_FAILED` 或 `REJECTED`。错误通过集中 `AgentErrorCode` 表达。外部响应只包含稳定码和安全通用文案，不包含系统 Prompt、模型原始响应、异常详情、密钥或堆栈。

工具失败后仍允许第二轮给出受限回答，但最终状态保持 `TOOL_FAILED`，并必须携带 limitation 或 warning。

## 12. Trace 与日志

Trace 只记录 UUID、事件类型、时间、工具名称、成功/失败状态、安全错误码和耗时。它不记录用户 ID、用户消息、会话内容、上下文数据、工具参数/结果、模型回答、Prompt 或异常文本。本阶段 Trace 只驻留内存，不落库。

结构化日志同样只记录 request/trace UUID、最终状态和工具调用数。

## 13. 安全与隐私

- 工具由服务端显式注册，模型不能执行任意函数。
- 所有工具再次执行输入、输出和意图权限校验。
- Agent 不接收 Garmin Token、API Key、数据库密码或真实 Provider payload。
- 响应不得暴露内部 Prompt、凭据、堆栈或敏感身份字段。
- 医疗诊断和“已修改计划”声明会被确定性拒绝。
- 本阶段所有测试数据均为虚构数据。

## 14. 后续扩展点

v0.11.0-B 计划接入只读训练工具与更完整的 Agent Context Builder。后续阶段可在不改变核心契约的前提下增加：经认证的内部入口、真实 Provider Gateway、更多只读产品工具、持久化审计策略和用户确认流程。任何写操作都必须另行设计确认、权限、幂等和事务边界。

## 15. 验收标准

- Agent 包可独立导入且不初始化网络或数据库。
- 无公共 Agent 路由、无迁移、无真实模型调用。
- 调用次数和上下文大小受限。
- 工具注册、权限、输入、输出和异常均有测试。
- 未知意图、无工具、单工具、多工具、工具失败、模型失败和非法输出均有确定性结果。
- Trace 和响应不包含敏感数据。
- 现有后端测试、安全边界检查和仓库隔离检查不退化。

## 16. 开源与私有边界

Agent 契约、Registry、Gateway 抽象、Mock、Validator、Trace、虚构测试和通用设计文档可以进入公开产品仓库。真实模型密钥、生产 Prompt 调优数据、真实对话、真实工具 Trace、用户 Runner State/训练计划、模型评测集、竞赛测试集与竞赛策略必须保持私有。任何真实凭据均不得写入代码、文档、Fixture、日志或环境示例。
