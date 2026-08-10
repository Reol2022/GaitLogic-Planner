# LangGraph Weekly Review

## 1. 为什么使用 LangGraph

v0.12 Coach 是一次请求内的只读工具编排，不需要持久暂停；v0.13 包含多节点、条件降级和人工审批恢复，图状态比手写大量 if/else 更容易验证节点边界。项目锁定 `langgraph==1.2.9`。

## 2. 项目中的概念对应

- State：`server/weekly_review_graph/schemas.py::WeeklyReviewState`。
- Node：`server/weekly_review_graph/nodes.py::WeeklyReviewNodes` 的六个业务方法。
- Edge：`server/weekly_review_graph/workflow.py::build_weekly_review_graph()` 中的 `add_edge`。
- Conditional Edge：`_after_validation()` 决定 finalize 或 fallback。
- Checkpointer：`server/adaptive_workflow/checkpointer.py::SQLAlchemyCheckpointSaver`。
- Interrupt：`server/adaptive_workflow/graph.py::request_human_approval()`。
- Command/Resume：批准服务在恢复审批图时使用 LangGraph `Command(resume=...)`。

```text
START
  |
load_weekly_facts
  |
evaluate_weekly_rules
  |
retrieve_training_knowledge
  |
generate_weekly_review
  |
validate_weekly_review
  | valid                     | invalid/provider failure
  v                           v
finalize_weekly_review <- fallback_weekly_review
  |
 END
```

## 3. Adapter 与复用

`server/weekly_review_graph/adapters.py` 把已有 `AgentLLMGateway` 适配为 `AgentGatewayWeeklyReviewGenerator`，并把已有 `RetrieveTrainingKnowledgeTool` 适配为 `KnowledgeToolWeeklyRetriever`。没有建立第二套 Provider 或 RAG。

## 4. Validator 与 Fallback

Validator 检查重复或不存在的知识引用以及不安全声明。失败后不会返回被拒绝的模型正文，而是用 Weekly Facts 构造确定性 Fallback。最终 `WeeklyReviewResult` 再从 State 中取回 canonical warnings、limitations 和 references。

## 5. Checkpoint 与恢复

`SQLAlchemyCheckpointSaver` 实现 `get_tuple`、`list`、`put`、`put_writes`、`delete_thread`，分别读写 checkpoint 与 pending writes。生产恢复依赖 MySQL，而不是进程内字典。thread_id 是工作流标识，不从客户端 user_id 推导权限。

## 6. 测试

`tests/test_weekly_review_graph.py` 覆盖正常图、RAG 禁用、知识失败、Provider 失败、未知引用、Validator 拒绝、Fallback 和公共结构。`tests/test_adaptive_plan_hitl.py` 覆盖 interrupt、resume 和持久 checkpoint（数据库环境缺失时会明确 skip）。

## 7. 常见错误

不要把一个函数机械拆成十几个无意义节点；不要把整个 SQLAlchemy Session 放入 State；不要把 API Key、Prompt、原始 Tool Result 写入 checkpoint；不要在恢复时信任客户端提交的 user_id。

## 8. 面试回答

30 秒回答：我只在需要显式状态、条件边和人工暂停恢复的 v0.13 使用 LangGraph。周复盘图负责可观察的只读编排，审批图用 interrupt 和持久 checkpointer 跨请求恢复。数据库写入仍由领域服务事务控制，而不是由图节点随意执行。

追问“为何不手写 Agent Loop”时回答：手写循环适合简单调用，但暂停恢复、pending writes、条件分支和 checkpoint 一致性会变成自建状态机；LangGraph 提供标准协议，我只实现项目需要的 SQLAlchemy Saver 和领域节点。
