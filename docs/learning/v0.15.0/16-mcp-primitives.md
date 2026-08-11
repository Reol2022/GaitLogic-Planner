# Tool、Resource 与 Prompt 的职责边界

Tool 用于受控执行：GaitLogic 的四个 MCP Tool 都是只读适配器，训练事实 Tool 依赖可信身份上下文，知识 Tool 复用既有 RAG。Resource 用于公开、稳定、可发现的内容投影；本阶段只公开训练知识目录、允许的知识文档和能力说明。Prompt 是 Host 可读取的交互模板，不是服务端任务调度器。

这三种 MCP primitive 不能替代 Tool Policy、Runner State 规则、Validator 或训练计划审批。规则与权限仍由既有服务端领域层决定，MCP 只负责协议适配。
