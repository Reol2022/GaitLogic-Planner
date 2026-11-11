# Garmin RPE 与单次训练事实链路（2026-11-11）

## 状态与边界

本轮为本地实现和合成验收，未部署、未执行生产迁移、未写入生产训练数据、未执行真实回填。线上基线仍是MCP `0.16.8-facts-v3.2`及此前UTC筛选补丁。

指定真实样本仅用于私有验收。SSH解锁后已通过只读事务核对日志与设备活动关联，并读取相关活动详情及分段；确认已知RPE字段存在，转换结果与用户陈述一致。该日志实际关联多条活动，现存分段未覆盖全部上游分段。具体引用、评价值和运动数据不写入公开报告或Fixture。此结果仅证明关联与上游读取；尚未执行真实样本的生产落库或回填，不宣称完整持久化验收通过。

## 根因审计

1. 当前认证使用garminconnect/garth持久化会话，沿用已有中国区连接，不跨区域重试。
2. 活动列表调用`get_activities(offset, 100)`，在本地按UTC窗口筛选。列表刻意不逐条同步请求分段，以避免之前的N+1网络请求和同步超时。
3. 详情调用`get_activity(activityId)`；此前解析器按列表扁平字段读取，而详情的关键指标通常嵌套于summaryDTO。新实现先展开已知summary，再规范化。
4. ProviderActivity及入库映射此前没有RPE字段，WorkoutLog只有手工RPE；因此有活动摘要不代表同步了自我评价。
5. 仓库当前没有活动FIT下载/解析链路。本轮不增加未经验证的FIT字段解析，不把缺失接口字段推断为零。
6. MCP已有`get_training_detail`，但Coach内部工具注册表没有对应详情能力；且个人分析的6个通用预加载占满6次预算。仅改Prompt无法解决。
7. 新建Garmin日志此前复制计划类型到workout_type，不能据此证明实际训练类型。

## RPE契约

仅支持已知的`summaryDTO.directWorkoutRpe`及同名顶层字段。上游项目资料描述该字段为显示分数的十倍，严格将10/20/…/100转换为1/2/…/10；不是根据数值大小猜刻度。不识别未确认的别名，不四舍五入未知刻度，不把directWorkoutFeel当作RPE。

参考：[python-garminconnect项目讨论](https://github.com/cyberjunky/python-garminconnect/discussions/198)、[garminconnect-js项目的直接验证记录](https://github.com/DynamicsNinja/garminconnect-js/blob/main/AGENTS.md)。这些是上游实现资料，不等同Garmin官方稳定协议保证，更不替代当前中国区账户的真实核验。

证据包含schema_version、source、fact_kind、raw_field、raw_value、原刻度/规范刻度、value、fetched_at、missing_reason。Garmin RPE仍是**用户在Garmin中填写的主观评价**，不是设备测量或独立验证事实。

缺失原因包括NOT_PROVIDED、INVALID_VALUE、DETAILS_NOT_FETCHED、DETAIL_FETCH_FAILED、MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING。null不转零；历史有效值与最近一次失败/缺失状态分开保留。

## 存储及覆盖策略

复用现有JSON来源字段，不新增业务表或数据库列，因此无需SQL/ORM结构迁移：

- ExternalActivity.field_sources_json：`rpe_evidence`保存有效或首次缺失的规范证据；`rpe_last_attempt`记录最近请求结果；`details_fetched_at`供刷新冷却。
- WorkoutLog.rpe：保存有效单次训练评价。field_sources_json.rpe标记garmin或manual；rpe_evidence记录生效来源；garmin_rpe_evidence记录最近Garmin尝试。
- 手工修改以及明确的手工清空优先。原有非空且来源未知的值保守视为人工值，不自动覆盖。
- 多活动聚合不平均、相加或挑选某条RPE充当整堂课RPE；需用户给出整堂训练评价。
- 列表同步、详情失败或空分段响应不清空既有分段。数据保留不代表已证明上游分段完整。

新增JSON字段通过只读输出白名单序列化；不导出任意JSON键、原始错误、GPS或自由文本健康内容。

## 同步、重新同步与回填

普通同步最多为最近28天中的1条需要刷新的活动补取详情，15分钟新鲜度冷却；每个详情/分段请求设置15秒超时并恢复原客户端超时。详情失败不阻断已有列表摘要入库。历史批量补取走显式预览/刷新，避免普通同步重新出现大量逐活动网络请求。该上限是请求数量/单请求超时控制，不是整个同步绝对时长保证，真实网络耗时尚待验收。

显式刷新使用`garmin_detail_refresh_service.refresh_details`，仅处理当前用户已存活动与已有关联日志，不创建课表、不激活周期、不新建训练日志。范围最多28个自然日、每批最多30条，返回has_more，避免把截断当完整。调用方管理事务，单活动使用savepoint；刷新后的Runner State当前查询会读取最新日志。独立刷新不伪造原同步任务结果，也不自动补造历史状态快照。

管理脚本`scripts/refresh_garmin_activity_details.py`默认只读预览。先核对脚本打印的数据库目标元数据，再审查候选引用。示例日期/用户ID必须由管理员替换为实际授权目标：

```text
python scripts/refresh_garmin_activity_details.py --user-id <授权用户ID> --start <YYYY-MM-DD> --end <YYYY-MM-DD>
```

实际应用需单独授权，并且显式提供每个`--activity-id`、`--apply --confirm REFRESH_GARMIN_DETAILS`。不要将凭据放入命令、文档或Git。分批预览/应用可恢复；重复刷新不增加活动、关联或日志。脚本会刷新已有评价与存储分段，不代表可以验证任意比赛分析的结论。

## Coach / MCP / Runner State

- MCP继续保持六个既有工具，对外保留`get_training_detail`兼容名称，没有新增重复MCP工具。新增输出是兼容性字段。
- Coach内部新增`get_workout_detail`，复用同一用户隔离、活动选择与100段上限的查询。Coach上下文额外限制24段，截断时segments_complete=false；不把lap视为一公里。
- 单次实际训练分析不再路由为“今天该怎么跑”；今天/昨天/指定日期有明确的自然日窗口。显式引用或唯一完整日记录可自动读取详情，多记录不自动选一条。
- 单次分析先加载实际训练、状态、周期背景及质量信息，预留工具预算；没有计划或RPE不等于其他训练事实不可解释。总体预算及Validator不放宽。
- 详情返回已存的速度、心率、活动功率、RPE、计时/移动/经过时间。暂停总量仅在可计算时以elapsed-timer派生，并明确不是逐次暂停时间线。当前没有逐段功率字段，不补造。
- 训练API与Coach增加planned_training_type/actual_training_type。Garmin日志未经明确实际分类来源时保留UNKNOWN；不据活动标题、计划类型或平均配速自动断定法特莱克/阈值/比赛。
- Runner State沿用现有RPE平均与覆盖率计算，没有修改规则阈值或新增恢复评分。恢复数据仍按可用事实、来源与新鲜度表达，不把低负荷风险等同恢复充分。
- 当前周期查询增加is_active与已持久化target_result；已有赛事日期、阶段继续使用数据库字段。历史参考周期不标记active；聊天自述不写入正式目标。

## 变更文件

| 文件 | 内容 |
| --- | --- |
| server/integrations/activity_provider/base.py | 详情/RPE/分段获取状态的Provider字段 |
| server/integrations/activity_provider/garmin.py | 嵌套详情解析、RPE规范化、分段读取与有界超时；保留既有UTC修复 |
| server/integrations/activity_provider/self_evaluation.py | RPE契约、来源白名单、覆盖策略 |
| server/services/garmin_sync_service.py | 有界补取、来源持久化、日志RPE更新、保留分段、查询用户过滤 |
| server/services/garmin_detail_refresh_service.py | 显式、受限、默认预览的详情刷新 |
| scripts/refresh_garmin_activity_details.py | 分批预览与明确确认应用 |
| server/services/workout_log_service.py、excel_import_service.py | 标记人工/Excel导入RPE修改，避免后续Garmin覆盖 |
| server/services/training_fact_policy.py | 保守的实际类型读取 |
| server/services/training_load_service.py、server/schemas/training_read.py | 查询返回RPE来源及计划/实际类型 |
| server/mcp/facts_v2.py、server/mcp/schemas.py | 详情速度/暂停/RPE和近期训练来源 |
| server/agent/tools/workout_detail.py、factory.py | Coach详情工具及注册 |
| server/agent/schemas.py、training_context_builder.py | 有界详情上下文及依赖取数 |
| server/agent/required_facts_policy.py | 单次事实优先与调用预算预留 |
| server/agent/coach_task_classifier.py、training_date_range.py | 实际分析路由及日期窗口 |
| server/agent/tools/planning_tools.py、schemas.py | 活跃周期、数据库目标与RPE查询字段 |
| server/agent/prompts.py | 限制相关、实际事实优先，不伪造强度或分段 |
| tests/test_garmin_rpe_pipeline.py、test_garmin_rpe_mysql.py | 纯合成单元和真实MySQL链路回归 |

本轮没有改动生产配置、Garmin凭据、无关AI课表/Web改动或受保护的upgrade_v0130_adaptive_plan.py。

## 验收记录（需按最后运行结果更新）

- 单元/Coach/MCP/OAuth/状态/知识检索/可观测最终定向组：270 passed、1 skipped，23.40秒。不与下述重叠分组重复累加。
- RPE独立合成组：24 passed、0 skipped，1.67秒。
- 真实本机3307受限账号、临时gaitlogic_test_*库：最终24 passed、0 skipped，48.02秒。覆盖RPE持久化与修改、实际Coach Context自动详情、双用户、真实TCP OAuth/刷新撤销和MCP事实/恢复接口；包含定向组因缺少测试URL跳过的OAuth路由用例补测。原测试轮次曾因漏传limit/测试库前缀约束失败；之后又因工具调用预算耗尽发现真实缺陷，已增加事实优先政策并保留失败场景为回归。
- 同步物质变更组：28 passed、0 skipped，27.35秒；该组需要创建隔离测试库，先前在受限账号下的13项skipped已单独在本机管理账号隔离建库后验证，未将跳过当通过。
- compileall尝试因Windows __pycache__写权限失败；内存语法编译PASS，不将文件写入失败伪称成功。
- diff检查：无空白错误，存在原有CRLF提示；不是测试失败。
- 真实指定Garmin样本：关联与上游RPE只读核验PASS；确认上游分段可读且存储分段尚不完整。真实样本的重新同步、分段持久化和生产MCP值对照NOT EXECUTED。

## 尚未完成

1. 代码发布后仍需单独确认真实样本详情更新；关联多活动时保留活动级评价，不将其自动平均或合并为整堂课评价。
2. 生产持久化和MCP值对照需在明确授权的重新同步后验收，不以上游读取或合成测试代替。
3. 本次发布流程获得代码上线授权；单样本应用及28天回填不在此授权范围内，当前不执行。
4. FIT解析、逐秒心率/功率/逐次暂停、完整个人强度基线和更深入训练分类未实现；不得以本轮可读取字段替代这些能力。
