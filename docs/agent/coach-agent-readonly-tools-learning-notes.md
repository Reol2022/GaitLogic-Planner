# Coach Agent 只读训练工具学习笔记

## 为什么 Tool 不能直接查 ORM

ORM 带有 lazy relationship、Session 生命周期和内部字段。让模型工具直接处理 ORM 会扩大数据暴露面，也容易产生 N+1。正确边界是 Service 决定查询口径，Tool 只做脱敏、裁剪和强类型输出。

## Tool 与 Service 的区别

Service 是产品领域能力，例如 Runner State 计算、训练事实归一化和规则命中。Tool 是 Agent 的最小权限适配器，不应复制领域算法。若缺少合适的读取入口，应在对应 Service 增加小型只读方法。

## 为什么参数中没有 user_id

模型生成的 arguments 不可信。身份必须来自认证后创建的 `AgentRequest`，进入 `AgentContext.user_id`。所有 Service 查询继续使用该 ID 过滤。Pydantic `extra=forbid` 会拒绝模型试图注入的 `user_id`。

## 无数据为什么不是异常

数据库查询成功但没有活动周期、计划或日志，是业务状态 `NOT_FOUND`；覆盖不足是 `PARTIAL/UNKNOWN`。只有查询、序列化或依赖故障才是 `AgentToolStatus.FAILED`。这能防止把数据库异常伪装成“今天没有训练”。

## 日期范围为什么必须有限

固定 1–28 天和 1–14 条快照既避免大查询和大 Context，也限制模型探测历史数据。历史详情不开放任意 snapshot_id；旧快照直接读取保存摘要，不套用新规则重新计算。

## Context Builder 如何工作

Builder 根据 Intent 查 `_PRELOADS`，逐项通过 Registry 调用，记录 Context Trace 并写入结构化字段。失败只添加 missing reason。UNKNOWN Intent 完全不加载训练数据。

裁剪先应用条目上限和字符串上限，再按低优先级移除规则、历史、近期详情与重复 Tool Result data。裁剪结果增加 limitation，过程不调用模型，因此相同有效输入得到相同训练内容裁剪结果。

## 如何防止 N+1

近期训练使用一个区间查询并复用计划 join；周期使用 `selectinload` 一次加载 blocks；快照历史只查询当前页摘要列。新增工具前应先确认 Service 是否已经提供批量读取能力。

## 如何测试只读性

除检查代码外，还应：

1. 在初始化虚构 Fixture 后监听 SQL；
2. 对 INSERT/UPDATE/DELETE 立即失败；
3. 调用工具前后比较关键表数量；
4. 确认 Session 没有 commit/flush；
5. 使用两个虚构用户验证结果隔离。

## 如何增加第九个工具

先证明领域 Service 有安全只读入口；定义禁止额外参数的输入和脱敏输出 Schema；实现 AgentTool；配置 Intent；增加用户隔离、只读、边界、裁剪和失败语义测试；最后显式更新 `COACH_AGENT_TOOL_NAMES`。Factory 的精确集合断言会阻止工具悄悄进入生产。

## 验收清单

- [ ] 工具集合精确为批准的八项；
- [ ] 所有工具只读且无需确认；
- [ ] user_id 仅来自 Context；
- [ ] 不返回 ORM、payload、凭据和内部规则表达式；
- [ ] Intent 预加载符合最小权限；
- [ ] Context 裁剪有 limitation；
- [ ] Context/Model Tool Trace 可区分；
- [ ] 双用户隔离和 SQL 只读测试通过；
- [ ] A 阶段与完整测试不退化；
- [ ] 无公共 API、前端、迁移、真实 Provider 或 Garmin 调用。
