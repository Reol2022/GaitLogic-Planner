# v0.13 面试问答

## 1. 为什么 v0.13 使用 LangGraph，v0.12 没有？

**30 秒回答：**v0.12 Coach 是单请求只读 Tool Calling，已有显式编排足够；v0.13 出现多节点条件分支、人工暂停和跨请求恢复，LangGraph 的 State、conditional edge、interrupt 和 checkpointer与需求直接对应。

**追问：与手写 Agent Loop 区别？**手写 Loop 可以完成简单调用，但 checkpoint 协议、pending writes、恢复和条件边会变成自建状态机。这里仍保留领域服务和事务，不把业务都塞进图。

## 2. State、Node、Edge 在代码哪里？

**30 秒回答：**State 是 `WeeklyReviewState`；Node 是 `WeeklyReviewNodes` 方法；Edge 和 conditional edge 在 `build_weekly_review_graph()`；审批图的 interrupt 在 `request_human_approval()`，持久化是 `SQLAlchemyCheckpointSaver`。

**追问：State 能否放 Session？**不能。Session 生命周期和序列化不适合 checkpoint；State 放严格可序列化数据，数据库操作留在服务层。

## 3. 为什么计划修改需要 HITL？

**30 秒回答：**训练计划修改有真实后果。模型只形成 Proposal，用户明确批准后，服务端再验证所有权、规则、锁定和版本，并在事务内写入。这样授权来源、决策边界和执行职责彼此独立。

**追问：前端按钮算授权吗？**不够。API 必须从 JWT 注入用户并在数据库重新查询资源，不能信任客户端 user_id 或 after 数据。

## 4. 如何保证重复确认不重复修改？

**30 秒回答：**批准事务锁定 Proposal 和目标计划，检查状态与 base_plan_version；已应用 Proposal 返回既有版本；新版本记录与状态在同一事务提交。并发请求只有一个能完成首次应用。

## 5. 服务重启后审批怎么办？

**30 秒回答：**生产图使用 `SQLAlchemyCheckpointSaver` 保存 checkpoint 与 pending writes，以 thread_id 找回状态，再通过 `Command(resume=decision)` 恢复。不是依赖进程内字典。

## 6. Plan 和实际训练如何保持一致？

**30 秒回答：**不把二者变成同一份数据。Plan 是期望，WorkoutLog 是事实，通过显式 planned_workout_id 优先关联；聚合层计算完成、偏差和临时训练。计划版本保存修改历史，日志不被 Proposal 覆盖。

## 7. Agent 出错如何追踪？

**30 秒回答：**SafeTracer 为 weekly facts、rules、RAG、LLM、validator、fallback、transaction 建父子 Span，记录耗时、状态和安全错误码，不记录 Prompt 或训练正文。看 Span 链可以区分 Provider、RAG、Validator 或 DB 故障。

## 8. Rules、RAG、LLM 各负责什么？

**30 秒回答：**Weekly Facts 和 Rules 决定可验证事实与安全边界；RAG 只提供训练知识依据；LLM 负责解释和编排；Validator 阻止引用幻觉和越权声明；Fallback 在模型失败时保留确定性结果。

## 9. 为什么没有 Multi-Agent？

**30 秒回答：**目前事实、规则、知识和写入边界可以由一个显式图清楚表达，多 Agent 会增加通信、权限和评测面。只有当独立职责需要各自工具与状态、且单图复杂度无法维护时才拆。

**追问：将来怎么拆？**可拆只读 Review Agent 与 Proposal Agent，但二者共享 canonical facts，写入仍只经过 Approval Service，不能给任何 Agent 通用写权限。

## 10. 代码出过什么问题？

Windows 完整测试曾因 Git 行尾归一化使复制到临时目录的 Corpus Manifest 哈希失效。修复没有放宽生产校验，而是让测试 Fixture 根据自身复制后的 Corpus 重建派生 Manifest，体现了源数据和派生产物的边界。
