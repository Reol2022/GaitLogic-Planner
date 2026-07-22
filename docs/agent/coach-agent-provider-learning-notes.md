# Coach Agent Provider 学习说明

## 从 API 到回答

入口在 `server/api/routes/coach.py`。认证依赖注入当前用户和 Session，`CoachAgentQueryService` 用服务器身份创建 `AgentRequest`，再创建请求级 Dependencies、八个只读工具的 Registry 与 `AgentTrainingContextBuilder`。TODAY Context 会先执行五个权威工具，然后 `GaitLogicCoachAgent` 调用 Gateway，最后 Validator 决定接受还是进入 Fallback。

重点代码路径：

- 配置：`planner_core/config.py`
- 公共 Schema：`server/schemas/coach_agent.py`
- API：`server/api/routes/coach.py`
- 组合服务：`server/services/coach_agent_query_service.py`
- 额度/Usage：`server/services/coach_agent_usage_service.py`
- Provider：`server/agent/providers/openai_compatible.py`
- URL 检查：`server/agent/providers/security.py`
- Prompt：`server/agent/prompts.py`
- TODAY 校验：`server/agent/today_recommendation.py`
- Fallback：`server/agent/fallback.py`

## 为什么 Provider 不在 Agent Core 中

`AgentLLMGateway` 是边界。Core 只理解结构化 Context、工具定义和 `AgentModelOutput`，不 import 厂商 SDK。这样 Fake Gateway、真实 OpenAI-compatible Adapter 和未来其他 Provider 都遵守同一编排与校验，不会让网络配置渗入训练规则。

既有 `ai_plan_service.py` 虽然也使用 OpenAI-compatible SDK，但它同时管理 AI Plan Job、Quota、Prompt 输入输出和草稿写入，业务语义与只读 Coach 不同，因此没有直接复用。C 阶段只复用已安装的 SDK、Settings 风格和安全错误响应约定，没有改变 AI Plan 对外行为。

## 如何配置开发环境

复制 `.env.example` 的 Coach 变量到本地未跟踪 `.env`，填写测试 Provider 的 URL、模型和本地密钥，最后显式设置 `COACH_AGENT_ENABLED=true`。不要把 `.env`、Key 或真实 Provider 响应提交到仓库。

本地 Fake Provider 只有在 `APP_ENV=development` 且 `COACH_AGENT_ALLOW_LOCAL_PROVIDER_IN_DEVELOPMENT=true` 时允许；生产环境不要打开该开关。自动测试通过 `client_factory` 或 `MockAgentLLMGateway` 注入虚构响应，不需要任何网络。

## 如何测试 Provider

`tests/test_agent_provider_gateway.py` 覆盖严格 JSON、原生工具调用、429/5xx、连接/读取超时、401、非法结构、超长输出和日志脱敏。`tests/test_agent_provider_security.py` 覆盖 URL scheme、私网、元数据地址、凭据和重定向设置。新增 Provider 时应继续复用这些契约测试，尤其不能把原始异常正文带进公共响应。

## 如何增加工具

工具必须继承现有只读 `AgentTool`，输入输出使用 Pydantic，注册到 `build_coach_agent_tool_registry`，明确 allowed intents，并补充权限、参数、用户隔离和无写入测试。Provider Adapter 不应知道工具 Dependencies，也不能接收 Session 或用户 ID 参数。

## 如何排查降级

1. 查看公共 `provider_status` 和 limitation 的安全码；
2. 查看脱敏运维日志中的 capability、Provider/模型别名、耗时和安全错误码；
3. 确认 Coach 启用开关、服务端 Key、受控 URL 和模型配置；
4. 检查权威工具是否返回 FAILED 或数据不足；
5. 检查 Validator 是否因 decision、Evidence、数值、计划状态或安全措辞拒绝。

不要记录或打印用户 message、完整 Context、工具数据、Authorization Header 或 Provider 原始响应来排错。

## Quota 说明

当前限流是进程内、按用户隔离的滚动 24 小时窗口和冷却期。它适合 C 阶段单实例保护，但不保证多进程全局一致，也不会持久化重启前计数。既有 AI Plan quota 与计划任务表强耦合，直接复用会改变旧业务或需要迁移，因此本阶段没有这样做。

## 项目负责人验收清单

- [ ] 客户端不能提交用户 ID、模型、Provider、URL、Key、Prompt 或 tools；
- [ ] TODAY 固定加载 `evaluate_today_workout`；
- [ ] decision、计划状态、data quality 和 Evidence 均通过确定性校验；
- [ ] Provider 失败返回 DEGRADED，而不是空白或 500；
- [ ] 未开放 WEEKLY 不加载训练 Context、不调用模型；
- [ ] 没有 commit/flush、计划修改、训练日志写入、快照或 Garmin 触发；
- [ ] 自动测试不访问真实网络、不使用真实 Key 或用户数据；
- [ ] 日志与 API 不包含 Prompt、Context、原始响应、思维链和用户身份。

## 当前限制

没有前端 Coach 页面、Weekly Review Agent、写工具、长期记忆、Trace 持久化、Streaming、RAG、多 Agent 或自动计划调整。下一阶段应先增加用户确认流程，而不是扩大模型权限。
