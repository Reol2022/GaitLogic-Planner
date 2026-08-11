# MySQL Composite Index Width and Hash Key Design

## 问题

`adaptive_workflow_checkpoint_writes` 需要用线程、命名空间、检查点、任务和写入序号确定一条 pending write。旧唯一键直接包含完整的 `task_path VARCHAR(512)`：

```text
(thread_id, checkpoint_namespace, checkpoint_id, task_id, task_path, write_index)
```

在 `utf8mb4` 下，一个字符最多占四个字节。四个 `VARCHAR(128)` 与一个 `VARCHAR(512)` 的最坏索引宽度为 `4 × 128 × 4 + 512 × 4 = 4096` bytes，超过 InnoDB 在 MySQL 5.7/8 常见的 3072-byte 上限。因此，建表失败不是 SQLAlchemy 或 LangGraph 的运行时错误，而是实际 DDL 无法被目标数据库接受。

## 设计

完整 `task_path` 仍以 `VARCHAR(512)` 保存。新增内部字段 `task_path_hash BINARY(32)`，它是 `SHA-256(task_path.encode("utf-8")).digest()` 的固定 32-byte 二进制摘要。新唯一键为：

```text
(thread_id, checkpoint_namespace, checkpoint_id, task_id, task_path_hash, write_index)
```

最坏宽度是 `4 × 128 × 4 + 32 = 2080` bytes，低于限制。Hash 只用于压缩数据库索引键，不是业务 ID，也不会出现在 REST API、MCP、Agent Tool、Trace、Metrics、Prompt、评测报告或前端。

不能靠缩短或截断 `task_path` 解决：这会改变 LangGraph 路径的完整存储或使不同路径共享前缀后被错误视为同一条写入。也不能删除唯一约束，因为幂等写入语义依赖它。

## 写入与查询不变量

唯一的 Hash helper 是 `planner_core/adaptive_plan/checkpoint_identity.py` 中的 `compute_task_path_hash`。ORM 的 `before_insert` 与 `before_update` 事件在持久化边界同步 Hash；调用者不能自行提供 Hash。

`SQLAlchemyCheckpointSaver.put_writes` 查询时先按新 Hash 缩小候选，再用完整 `task_path == original_task_path` 作最终精确比较。因此 SHA-256 的理论碰撞不会被静默当作相同路径。完整路径仍用于业务读取、恢复和审计。

SHA-256 不是数学上的绝对无碰撞保证；这里选择它是为了将实际可行风险降到极低，同时保留原文 equality 校验。

## 既有数据库升级

新库由 SQLAlchemy Model 与 `sql/schema.sql` 直接创建正确结构。已有 v0.13 数据库使用：

```powershell
python scripts/upgrade_v0160_adaptive_checkpoint_hash.py upgrade
```

脚本依次添加 nullable `BINARY(32)` 列、用 Python 的同一 UTF-8/SHA-256 helper 回填、确认无 NULL、删除旧唯一键、设置 NOT NULL，并创建新唯一键。它是前向迁移：旧索引在现代 MySQL 上本身不可重新创建，因此不存在安全的反向 downgrade。执行前应备份数据库，并在维护窗口内完成。

## 验证

测试覆盖了确定性、32-byte 长度、Unicode 和长路径、ORM insert/update 同步、重复路径幂等冲突、不同路径区分、SQLite schema 行为，以及 MySQL 旧表的回填和 `SHOW INDEX` 等价 inspection。MySQL 5.7/8 都应使用隔离随机测试库验证建表、迁移、写入、唯一性、checkpoint resume 与事务回滚。
