# GaitLogic Coach Agent 只读训练工具设计 v1

## 目标与边界

v0.11.0-B 将正式产品中的确定性训练事实接入 Agent Core。它不提供公共 API、不连接真实模型、不创建快照、不修改计划或日志，也不新增表或迁移。Agent 只负责调用已有服务、裁剪并组织 JSON-safe 上下文。

## 固定工具集合

| 工具 | 输入 | 主要输出 | 数据来源 |
|---|---|---|---|
| `get_runner_state` | `{}` | 当前状态、公开指标、Evidence、数据质量 | `RunnerStateService` |
| `get_runner_state_history` | `limit: 1..14` | 快照摘要 | `RunnerStateSnapshotService.list_snapshots` |
| `get_recent_training` | `days: 1..28, limit: 1..50` | 规范化训练事实与基础汇总 | 统一 WorkoutLog 查询 |
| `get_today_workout` | `{}` | PLANNED/REST_DAY/NO_PLAN/CYCLE_NOT_ACTIVE | 当前周期与今日计划服务 |
| `get_current_training_cycle` | `{}` | 活动周期和有界训练块 | 周期生命周期服务 |
| `get_training_rules` | 固定 scope | 启用且公开的规则摘要 | Training Rule Registry |
| `evaluate_today_workout` | `{}` | 既有 Daily Evaluation 决策与命中 | Rule Engine，`persist=False` |
| `get_training_data_quality` | `window_days: 7..28` | 字段覆盖、来源构成、新鲜度 | 统一训练事实查询 |

所有工具均为 `read_only=true`、`requires_confirmation=false`。参数 Schema 使用 `extra=forbid`，因此不能提交 `user_id`、任意规则包路径或无限日期范围。

## 身份、Dependencies 与 Session

`CoachAgentToolDependencies` 按请求构建并注入现有 SQLAlchemy Session。工具不创建、不提交、不关闭 Session。唯一身份来源为 `AgentContext.user_id`；Gateway 只能看到脱敏 Context，不能看到 Session 或 ORM。

Dependencies 复用 Runner State、Snapshot、Training Load、Planned Workout、Training Cycle 和 Training Rule 服务。历史列表只取摘要列，不加载完整 snapshot payload；近期训练使用单次有界日志查询，不逐项回查 ExternalActivity，因此不会形成 N+1。

## 输出与错误语义

业务数据状态统一为 `AVAILABLE / PARTIAL / UNKNOWN / NOT_FOUND`：

- `NOT_FOUND` 表示查询成功但没有业务记录；
- `UNKNOWN` 表示数据不足以得出确定结果；
- `PARTIAL` 表示存在数据但字段覆盖不完整；
- 技术异常由 Registry 转成 `AgentToolStatus.FAILED` 和安全错误码。

工具不返回 ORM、用户 ID、凭据、Garmin 原始 JSON、外部活动 ID、完整备注、快照 payload、回执或规则表达式。

## Intent 预加载

- TODAY：当前状态、今日计划、最近 7 天、14 天数据质量；今日评估保留为显式工具。
- WEEKLY：当前状态、7 条历史、最近 7 天、当前周期、14 天数据质量。
- EXPLAIN：当前状态、7 条历史、14 天数据质量。
- GENERAL：仅公开 GENERAL 规则摘要。
- UNKNOWN：不加载训练数据。

`AgentTrainingContextBuilder` 只能通过 Registry 调用工具。单工具失败写入 `missing_reasons`，不会中断其他预加载。

## 裁剪与 Trace

配置限制总字符、近期训练、历史、Evidence 和规则数。裁剪顺序为规则摘要、历史条目、近期条目、重复的 Tool Result data；当前状态、今日计划、数据质量与关键警告优先保留。发生裁剪时加入 `CONTEXT_TRIMMED` limitation，不调用 LLM 总结。

预加载记录 `CONTEXT_TOOL_STARTED/COMPLETED`；模型显式调用记录 `MODEL_TOOL_STARTED/COMPLETED`，并保留 A 阶段 `TOOL_CALL` 事件以兼容已有审计。

## 只读保证与隐私

Rule Engine 新增的只读入口在 `persist=False` 时不标记旧评估、不写命中、不创建调整草稿。测试使用 SQL 事件拒绝 INSERT/UPDATE/DELETE，并比较周期、计划、日志、快照、回执与同步任务计数。所有 Fixture 均为虚构数据。

## 当前限制

- 今日计划尚无结构化 segments、时长和心率目标；工具返回空值并声明 limitation。
- 周期没有正式完成度指标，因此 `progress=null`。
- 历史摘要只有风险数量，没有严重度；工具不反推风险级别。
- 当前无公开 `runner_state` scope 规则包时返回 NOT_FOUND。
- 无真实 Provider、公共 API、前端、写工具、长期记忆或多 Agent。

## 开源边界

可公开工具契约、裁剪、通用错误、虚构测试和文档。真实训练数据、状态、Context、Trace、规则命中、私有阈值、竞赛评测和 API Key 必须留在受控环境。
