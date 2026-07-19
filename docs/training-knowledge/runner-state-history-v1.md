# Runner State History v1

## 1. 目标与边界

当前状态是调用 `GET /api/runner-state/current` 时按需计算的即时结果；历史快照是用户明确执行手动保存后形成的不可变档案。C2.1 只提供后端存储、手动保存、列表和详情，不包含趋势前端、自动触发、删除、更新、计划调整或医学判断。

当前状态接口继续只读，不会因刷新页面而创建记录。历史详情直接返回保存时的内容，不用新规则重新计算旧状态。

## 2. 数据模型

ORM 模型为 `RunnerStateSnapshotRecord`，数据库表为 `runner_state_snapshots`。它与 Pydantic 的 `RunnerStateSnapshot` 名称分离。

| 字段 | 数据库类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | 否 | 自增主键 |
| user_id | BIGINT | 否 | 当前用户外键，删除用户时级联删除 |
| snapshot_date | DATE | 否 | 后端按 Asia/Shanghai 生成的保存业务日 |
| data_cutoff_date | DATE | 否 | 当前状态的计算截止日 |
| calculated_at | DATETIME | 否 | 当前状态实际计算时间 |
| created_at | DATETIME | 否 | 快照写入时间 |
| trigger_type | VARCHAR(32) | 否 | C2.1 固定为 MANUAL |
| trigger_reference | VARCHAR(128) | 是 | 为后续内部触发预留 |
| snapshot_schema_version | VARCHAR(64) | 否 | 快照结构版本 |
| ruleset_version | VARCHAR(64) | 否 | 保存时采用的状态规则版本 |
| distance_7d_km / distance_28d_km | DECIMAL(10,2) | 是 | 列表摘要；缺失保持 NULL |
| volume_trend / training_consistency / fatigue_state / training_phase | VARCHAR(32) | 是 | 列表摘要状态 |
| risk_flag_count | INT | 否 | 风险标记数量 |
| evidence_coverage / data_completeness | DECIMAL(6,4) | 是 | 证据覆盖程度与数据完整度 |
| snapshot_payload | JSON | 否 | 完整 Runner State JSON |
| payload_hash | VARCHAR(64) | 否 | 服务器内部 SHA-256 |

唯一约束为 `(user_id, data_cutoff_date, payload_hash)`；查询索引为 `(user_id, data_cutoff_date)` 和 `(user_id, created_at)`。所有查询都先限定当前用户，不支持跨用户排行。

## 3. 版本与完整内容

首版结构版本集中定义为：

```text
runner-state-snapshot-1.0.0
```

`snapshot_payload` 保存基础指标、派生指标、各状态推断、风险标记、Evidence、skipped signals、数据质量、limitations 和 inference metadata。保存内容不包含邮箱、手机号、密码、Garmin Token、API Key、数据库连接、原始设备响应或完整训练日志。

## 4. 规范化与稳定哈希

序列化先使用 Pydantic JSON 模式转换枚举、日期和时间，再对哈希副本执行以下步骤：

1. 深拷贝完整 payload，不修改状态对象或数据库保存内容；
2. 将枚举转换为稳定字符串，日期和时间转换为 ISO 8601；
3. Decimal 规范化为稳定十进制文本，拒绝 NaN 和 Infinity；
4. 字典键排序，列表保持业务顺序；
5. 使用 UTF-8、`ensure_ascii=false` 和固定 JSON 分隔符；
6. 对结果计算 SHA-256 十六进制摘要。

哈希明确包含截止日、结构版本、规则版本及所有语义状态。`calculated_at`、`created_at` 不参与哈希。现有 Runner State Schema 将计算时间同时命名为 `identity.generated_at` 和 `inference_metadata.calculated_at`，两条等价审计时间路径都从哈希副本排除，但完整 payload 仍保留原值。

因此键顺序或计算时间变化不会制造新状态；基础指标、Evidence、风险、数据质量、截止日或版本变化都会生成新哈希。

## 5. 保存、去重与并发

`RunnerStateSnapshotService` 复用 `RunnerStateService.get_current`，不复制 A/B 阶段统计和推断：

1. 计算当前状态；
2. 完整序列化并计算哈希；
3. 按当前用户、截止日和哈希预查询；
4. 已存在时返回旧记录，`created=false`、`duplicate=true`；
5. 不存在时插入不可变记录并提交；
6. 若并发请求命中指定唯一约束，执行 rollback，再查询并返回已成功写入的记录；
7. 其他完整性错误继续抛出，不伪装为重复。

相同状态重复保存只保留一条。同日状态变化允许多条；截止日、ruleset 或 schema 变化也允许新记录。当前状态计算或序列化失败时不会写入半成品。

## 6. API

### 手动保存

```http
POST /api/runner-state/snapshots
```

请求体可以省略或为 `{}`。额外字段被拒绝，客户端不能传 `user_id`、触发类型、版本、payload 或 hash。后端固定 `trigger_type=MANUAL`。

```json
{
  "snapshot": {
    "id": 901,
    "snapshot_date": "2026-07-15",
    "data_cutoff_date": "2026-07-15",
    "calculated_at": "2026-07-15T18:30:00+08:00",
    "created_at": "2026-07-15T18:31:00+08:00",
    "trigger_type": "MANUAL",
    "snapshot_schema_version": "runner-state-snapshot-1.0.0",
    "ruleset_version": "runner-state-rules-1.0.0",
    "distance_7d_km": 24.5,
    "distance_28d_km": 91.2,
    "volume_trend": "STABLE",
    "training_consistency": "MODERATE",
    "fatigue_state": "NORMAL",
    "training_phase": "UNKNOWN",
    "risk_flag_count": 0,
    "evidence_coverage": 0.8,
    "data_completeness": 0.75,
    "snapshot_payload": {"identity": {"runner_id": 901}}
  },
  "created": true,
  "duplicate": false
}
```

示例跑者和数值完全虚构。

### 列表

```http
GET /api/runner-state/snapshots?start_date=2026-07-01&end_date=2026-07-15&limit=30&offset=0
```

默认 limit 为 30，最大 100。排序为 `data_cutoff_date DESC, created_at DESC`。列表返回 `items/total/limit/offset` 和摘要字段，不加载或返回完整 payload。同日不同状态不折叠；每日最后一条聚合属于 C2.2。

### 详情

```http
GET /api/runner-state/snapshots/{snapshot_id}
```

详情按 `snapshot_id + 当前 user_id` 读取保存 payload，不调用当前状态服务。不存在或属于其他用户都使用同一 404，不泄露记录是否存在。

三个接口都不返回数据库 `user_id` 和 `payload_hash`，也没有 PUT、PATCH 或 DELETE。

## 7. 时间、事务和错误

业务时区固定复用项目的 `Asia/Shanghai`。数据库遵循项目现有 naive DATETIME 约定，写入前转换为上海本地时间并去掉 tzinfo；API 输出时恢复 `+08:00`。测试覆盖 UTC 与上海跨日边界对应的 `snapshot_date`。

日期范围反转返回参数错误，limit 超过 100 由 API 校验拒绝。写入错误必须 rollback；日志只记录内部用户 ID、快照 ID、触发类型、版本及 created/duplicate，不记录 payload、Evidence、身份信息或凭据。

## 8. 数据库迁移

项目不使用 Alembic。`scripts/upgrade_v0103_runner_state_snapshots.py` 提供 `upgrade` 和 `downgrade`，只创建或删除快照表。`checkfirst=False` 保证重复 upgrade 明确失败。`sql/schema.sql` 同步包含新安装所需 DDL。

迁移不修改训练日志、计划或 Garmin 表，不回填、不扫描、不创建默认快照。合并 master 前必须在隔离的 MySQL 8 测试库验证 upgrade、约束、JSON 读写和 downgrade，禁止在生产数据库试跑。

## 9. 不可变、隐私与当前限制

快照没有更新、删除接口；详情永远展示保存时的 ruleset、Evidence 和 limitations。C2.1 仅启用 MANUAL，不接 Garmin、定时任务或计划调整。它不调用大语言模型、不修改训练计划、不提供医学诊断，也不实现历史趋势页面。

公开仓库可包含模型、迁移、哈希、服务、API、虚构测试和本文档。真实用户快照、内测统计、竞赛实验和真实截图必须留在私有竞赛仓库；任何仓库都不得提交凭据或未脱敏训练记录。
