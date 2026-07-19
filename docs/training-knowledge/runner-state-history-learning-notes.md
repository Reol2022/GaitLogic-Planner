# Runner State 历史快照学习说明

## 1. POST 保存的完整数据流

入口位于 `server/api/routes/runner_state.py`。认证依赖先得到当前 `UserAccount`，路由不接收 user_id 或 trigger_type，然后调用 `RunnerStateSnapshotService.save_current`。

服务复用 A/B 阶段的 `RunnerStateService.get_current`：数据库训练记录先形成基础状态，再由既有推断层形成完整 `RunnerStateSnapshot`。C2.1 不查询第二套训练数据，也不复制推断公式。随后 serializer 将 Pydantic 对象转换为 JSON，哈希模块生成稳定 SHA-256，服务提取列表摘要并写入 ORM 模型。

```text
认证用户
  -> POST /runner-state/snapshots
  -> RunnerStateService.get_current
  -> serialize_runner_state_snapshot
  -> calculate_runner_state_payload_hash
  -> 预查重复
  -> INSERT + COMMIT
  -> API Detail + created/duplicate
```

## 2. 哈希包含什么

参与：data cutoff、基础和派生指标、各状态、风险、Evidence、skipped signals、data quality、limitations、ruleset version 和 snapshot schema version。

不参与：计算时间和数据库创建时间。实际 Schema 中 `identity.generated_at` 是 calculated_at 的同义来源，也按非语义计算时间排除。排除仅发生在深拷贝的哈希输入中，数据库 JSON 不丢字段。

这样做的原因是：同一状态在 18:00 和 18:01 重新计算仍是同一训练状态；但数据、规则或结构真正变化时必须形成新档案。

## 3. 重复保存与并发请求

普通重复先被查询发现，直接返回旧 ID。并发时两个请求可能同时预查为空，所以数据库唯一约束是最终防线。输掉竞争的事务捕获指定唯一约束错误，先 rollback 清除失败事务，再按相同用户、截止日和 hash 重查。只有找到记录才返回 duplicate；外键失败等其他错误继续抛出。

唯一约束不是性能优化，而是正确性保证。应用层预查改善常见路径，数据库约束保证竞争条件下最多一条。

## 4. 列表和详情为什么分开

列表只加载摘要列，返回时间、版本、核心状态和质量数据，避免每行解析大型 JSON。详情才读取 `snapshot_payload`。历史详情绝不能调用 `RunnerStateService`，否则旧记录会被新数据或新规则改写，失去审计价值。

所有查询都带当前 user_id。通过别人的 snapshot_id 查询与不存在使用相同 404。

## 5. 如何升级 snapshot schema

1. 定义新的集中版本常量，例如 `runner-state-snapshot-2.0.0`；
2. 保持旧详情 JSON 可直接读取，不批量重写旧记录；
3. 更新 serializer、API 类型和兼容测试；
4. 如增加数据库摘要列，新增独立迁移及完整 downgrade；
5. 验证 schema version 变化会改变 hash；
6. 前端按记录自带版本解释旧 payload。

不要修改旧记录的 `snapshot_schema_version`。

## 6. 如何升级 ruleset

规则版本来自现有推断结果，不由快照服务猜测。发布新 ruleset 后，新保存记录自动带新版本并产生新 hash；旧快照保留旧版本和 Evidence。修改规则仍必须遵循 B 阶段权威规则流程，C2.1 不改 YAML 阈值。

## 7. 如何增加触发类型

枚举已经定义 MANUAL、GARMIN_SYNC、DAILY、PLAN_ADJUSTMENT、SYSTEM，但公共 POST 永远固定 MANUAL。未来触发必须新增内部专用调用入口，后端决定 trigger type/reference，并单独测试幂等、权限和事务；不能让客户端自由提交枚举，也不能在 C2.1 路由中顺手启用。

## 8. 如何编写和回滚迁移

项目没有 Alembic。新迁移脚本应：

1. 只操作本阶段表结构；
2. 提供明确 `upgrade(connection)` 和 `downgrade(connection)`；
3. 不使用 `IF NOT EXISTS` 掩盖重复部署；
4. 同步 `sql/schema.sql`；
5. 先在临时 SQLite/Mock 做静态与通用行为检查；
6. 再在随机命名、隔离的 MySQL 8 测试库执行 upgrade/JSON/约束/downgrade；
7. 绝不对生产库做验收试跑。

回滚命令由脚本的 `downgrade` 动作执行。回滚会删除快照表，因此正式环境执行前仍需标准备份和变更审批；C2.1 测试库中不生成历史回填数据。

## 9. 增加测试的方法

- 哈希测试直接构造完全虚构 payload，分别只改变一个语义字段；
- 服务测试注入假的 RunnerStateService，避免访问真实训练数据；
- 并发测试必须证明 rollback 后重查，而不只是测试预查询；
- API 测试覆盖认证、当前 user_id、额外请求字段、列表隐藏字段和详情不重算；
- 模型测试检查唯一约束、索引、JSON 和 ON DELETE CASCADE；
- MySQL 迁移测试必须使用临时测试库并如实报告 skip。

## 10. 项目负责人验收清单

- [ ] `GET /api/runner-state/current` 仍无数据库写入；
- [ ] POST 不接受 user_id、trigger_type、版本、payload 或 hash；
- [ ] 相同状态重复保存返回同一 ID；
- [ ] 同日状态变化可保存新记录；
- [ ] 并发唯一冲突执行 rollback 并返回 duplicate；
- [ ] 非唯一错误没有伪装成 duplicate；
- [ ] 列表默认 30、最大 100，且不加载 payload；
- [ ] 详情按 snapshot_id + 当前 user_id，且不重新计算；
- [ ] API 不返回 user_id、payload_hash 或敏感字段；
- [ ] migration upgrade/downgrade 在隔离 MySQL 测试库通过；
- [ ] 未接 Garmin、LLM、自动调整或历史前端；
- [ ] 测试数据全部虚构，公开边界检查通过。
