# Weekly Facts Data Quality v1

## 等级

| 等级 | 含义 |
|---|---|
| `COMPLETE` | 有计划和日志，关键统计字段完整，无匹配冲突，且有至少两条状态快照 |
| `PARTIAL` | 可计算，但有缺失字段、未匹配日志或状态历史不足 |
| `INSUFFICIENT` | 计划和日志均无有效事实 |
| `CONFLICTED` | 重复活动或同日多候选造成无法安全匹配 |

这不是模型预测概率。等级只描述输入证据能否支持确定性周事实。

## 诊断字段

- `missing_plan_days`：存在未匹配训练日志的自然日；它不表示每个空白日都应有计划。
- `missing_log_fields`：参与统计的距离或时长缺失。
- `unmatched_log_count`：无法关联计划的日志数。
- `ambiguous_match_count`：重复指纹或多个兼容计划的数量。
- `runner_state_sample_count`：窗口内有效状态快照数。

## 缺失值策略

- 缺失数值保持 `null`，不伪装为零。
- 合计只汇总存在的数值，同时在质量字段暴露覆盖缺口。
- 比率分母为零返回 `null`。
- Runner State 少于两条时趋势统一 `UNKNOWN`。
- 计划时长当前没有可靠结构化来源，服务返回 `null` 并增加
  `PLANNED_DURATION_NOT_STRUCTURED` limitation。

## 冲突策略

显式计划关联优先。无关联时只接受同日、主类型兼容且唯一的候选。歧义记录
不会被任意分配给某节计划，也不会重复计入训练统计。重复活动指纹同样只统计
第一条。该策略牺牲部分召回，换取事实层可解释和可复现。

## 隐私

质量信息仅包含字段名和计数，不包含原始训练正文、GPS、身份、凭据或
Provider 内容。公开案例目录 `evaluation/weekly_review/cases_v1.json`
全部是固定虚构元数据。
