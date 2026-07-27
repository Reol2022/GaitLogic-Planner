# Coach Agent Provider Gateway 设计 v1

## 目标与边界

v0.11.0-C 在 `AgentLLMGateway` 抽象后增加 OpenAI-compatible Chat Completions 适配器。Provider 只负责结构化工具调用与语言表达；Runner State、今日课表和只读规则评估仍是权威事实。此层不访问 ORM、不接收数据库 Session、不写训练业务数据，也不改变既有 AI Plan 的配置和调用路径。

## 配置

配置统一由 `planner_core.config.Settings` 从服务端环境读取：

- `COACH_AGENT_ENABLED`：默认 `false`，可独立于 AI Plan 启停；
- `COACH_AGENT_PROVIDER`：安全别名，默认 `openai-compatible`；
- `COACH_AGENT_API_KEY`：只允许服务端环境提供，仓库默认留空；
- `COACH_AGENT_BASE_URL`：受控 Provider 地址；
- `COACH_AGENT_MODEL`：受控模型名；
- `COACH_AGENT_THINKING_MODE`：仅允许 `unset`、`disabled`、`enabled`；
- `COACH_AGENT_RESPONSE_FORMAT_MODE`：仅允许 `json_schema`、`json_object`，默认 `json_schema`；
- `COACH_AGENT_CONNECT_TIMEOUT_SECONDS`、`COACH_AGENT_READ_TIMEOUT_SECONDS`、`COACH_AGENT_TOTAL_TIMEOUT_SECONDS`；
- `COACH_AGENT_MAX_RETRIES`：范围 0–1；
- `COACH_AGENT_MAX_OUTPUT_TOKENS`；
- `COACH_AGENT_ALLOW_LOCAL_PROVIDER_IN_DEVELOPMENT`：仅 development 显式开启时允许本地 Fake Provider。

`.env.example` 使用 `https://api.example.com/v1` 和 `example-model`，不包含真实凭据或生产地址。客户端请求 Schema 不包含上述任何字段。

## 请求转换

`OpenAICompatibleAgentGateway` 接收静态系统指令、用户消息、最小化 `AgentContext` 和当前 Intent 已允许的只读工具定义。传输前会：

1. 删除 `user_id`、`request_id`；
2. 将工具结果缩减为名称、状态、经验证数据、安全错误码和公开 warning；
3. 对文本中的邮箱和中国大陆手机号进行替换；
4. 将 Pydantic 工具输入 Schema 转为 strict function schema；
5. 强制 object 顶层 `additionalProperties=false`；
6. 为 TODAY 建立请求级 `available_evidence` Catalog；
7. 按 Intent 选择严格 Provider Schema：TODAY 使用最小叙事 Schema，其他 Intent
   使用 `ProviderAgentModelOutput`。

Gateway 不向 Provider 暴露 Dependencies、Python 类型、Session、Garmin 原始 payload、完整历史日志或写工具。

## 受控响应格式

`json_schema` 保持默认行为，按 Intent 发送严格的 Provider 内部输出 Schema。
`json_object` 只发送 `{"type": "json_object"}`，用于不支持最终 JSON Schema
Response Format、但支持 JSON Output 的兼容端点。

两种模式使用同一条安全响应链：

```text
Provider content
→ Intent 专用 Provider Schema 严格 Pydantic 校验
→ Evidence ID 严格校验与 Canonical materialization
→ 服务端装配 TODAY 确定性训练事实
→ AgentModelOutput 严格 Pydantic 校验
→ Deterministic Validator
→ 成功响应或安全 Fallback
```

`json_object` 不允许额外字段、未知枚举、缺失必需字段、Markdown 围栏、自然语言前后缀或截断 JSON。系统不修补模型 JSON，不调用第二个模型修复，不自动从一种响应格式重试为另一种格式，也不允许客户端覆盖响应格式。

DeepSeek-compatible 非思考模式的推荐组合是：

```env
COACH_AGENT_THINKING_MODE=disabled
COACH_AGENT_RESPONSE_FORMAT_MODE=json_object
```

这是显式部署配置，不会按 Provider 品牌、Base URL 或模型名推断。当前版本不读取或回传 `reasoning_content`，不支持完整思考模式工具链。

## Evidence Reference 协议

Provider 内部 TODAY 输出严格只有：

```json
{
  "answer": "Explanation only.",
  "summary": "Short explanation.",
  "key_evidence_ids": ["evidence_1"],
  "knowledge_reference_ids": []
}
```

decision、planned workout status、risk level、data quality、headline、warnings、
limitations 和 Canonical Evidence 都不属于模型输出。Gateway 使用服务端 Context
装配这些字段，再生成公共 `AgentModelOutput`。公共 API 仍使用 `key_evidence`。

Gateway 根据 `contextual_evidence()` 的原始顺序生成：

```json
[
  {"id": "evidence_1", "text": "Canonical Evidence A"},
  {"id": "evidence_2", "text": "Canonical Evidence B"}
]
```

ID 仅在当前请求中有效，不持久化、不进入 Trace、不返回客户端。模型只能选择
Catalog 中存在的 ID，不能返回 Evidence 文本。服务端拒绝未知、重复、空白、
大小写变化和超量引用，并按 Canonical 原始顺序还原最终 `key_evidence`，而不是
信任模型的措辞或排序。存在 Canonical Evidence 时空选择也会失败；只有 Catalog
为空时允许空数组。

该协议同时用于 `json_schema` 与 `json_object`。后者只降低 Provider 端响应格式
能力要求，不降低 Provider Pydantic Schema、Evidence 引用校验、公开
`AgentModelOutput` 或 Deterministic Validator。旧的自由文本 `key_evidence`
Provider 输出属于额外字段，会被严格拒绝并进入现有 Fallback。

## Training Knowledge Reference

启用 `retrieve_training_knowledge` 后，Provider 可以从当前请求的
`available_knowledge_references` 选择 `knowledge_n`，但不能返回 excerpt、Source
Title、URL 或文档正文。内部 Provider Schema 使用
`knowledge_reference_ids`，公共 API 则由服务端从 Canonical Tool Result 还原
`knowledge_references`；内部 ID、score、向量和路径均不公开。

`evidence_n` 与 `knowledge_n` 分别代表用户训练事实和通用训练知识。TODAY 中知识
只能解释确定性结果，不能改变 decision、risk、planned status、data quality、
warnings、limitations 或 Canonical Evidence。GENERAL 成功获得非空知识结果时必须
选择至少一个引用；Index 不可用或空结果时必须保留 limitation，不能声称使用了
知识库。完整协议见 `docs/rag/training-knowledge-reference-protocol-v1.md`。

模型尝试返回任何服务端权威字段同样属于额外字段并被拒绝。系统不把对象转换为
data quality 字符串，不接受 Union，不用 Prompt 修补事实类型。成功 Provider 路径
与确定性 Fallback 共用 `build_authoritative_today_facts()`，避免形成两套规则。

## 响应与工具调用

Provider 的原生 `tool_calls` 会转换为 `AgentToolInvocation`，未知工具、越权 Intent 和非法参数继续由 Tool Registry 确定性拒绝。最终文本必须是原始 JSON；Markdown 代码块、自由文本、额外字段、未知枚举、超长字段和非法工具参数均返回安全码 `AGENT_MODEL_OUTPUT_INVALID`，不回传原始响应。

## 超时、重试与错误

OpenAI SDK 自身重试关闭，由 Gateway 最多执行一次显式重试。只重试连接/读取超时、连接错误、HTTP 429 和 5xx；401、结构错误和校验错误不重试。公共错误只使用：

- `AGENT_PROVIDER_DISABLED`
- `AGENT_PROVIDER_UNCONFIGURED`
- `AGENT_PROVIDER_RATE_LIMITED`
- `AGENT_PROVIDER_UNAVAILABLE`
- `AGENT_MODEL_OUTPUT_INVALID`

日志仅记录 Provider/模型安全别名、状态、耗时、Token 数和安全错误码，不记录 Key、Authorization Header、Prompt、Context、原始响应或异常正文。

## 网络安全

Base URL 必须使用 HTTP/HTTPS，且不能包含账号密码或 fragment。生产默认拒绝 localhost、loopback、私网、link-local、保留地址、multicast、unspecified 和云元数据主机。HTTP 客户端禁止自动重定向，避免被转向未允许 Host。连接本地 Fake Provider 必须同时满足 development 环境和显式开关，自动测试使用注入的 Fake Client，不访问互联网。

## Trace

Provider Trace 仅新增 `PROVIDER_CALL_STARTED`、`PROVIDER_CALL_COMPLETED`、`PROVIDER_CALL_FAILED`。事件可含 provider/model alias、受控响应格式模式名称、耗时、Token 数和安全错误码，不记录响应 Schema 或正文；公共 API 只返回 `trace_id`，不返回事件列表。

## 当前限制

- 当前只有 OpenAI-compatible Chat Completions 适配器；
- 不支持 streaming、WebSocket、长期记忆或多 Agent；
- 未提供自动联网 smoke test；
- 本地地址开关只用于显式开发测试；
- Provider 可用性不改变确定性训练规则的权威性。
