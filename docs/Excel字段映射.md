# Excel字段映射

本阶段不实现 Excel 解析，只根据最新版 Excel 的核心 Sheet 设计数据库结构。

## 计划索引 -> planned_workouts

| Excel 字段 | 数据库字段 |
| --- | --- |
| 日期 | `date_text` / `workout_date` |
| 星期 | `weekday` |
| 阶段 | `phase_name` |
| 计划训练内容 | `planned_content` |
| 重点说明 | `focus_note` |
| 计划km估算 | `planned_distance_km` |
| 主类型 | `main_type_raw` / `main_type_normalized` |
| 源Sheet | `source_sheet` |
| 源行 | `source_row` |
| 月份 | `month_text` |
| 周次_统计 | `block_id`，关联 `training_blocks.id` |

## 训练日志 -> workout_logs

| Excel 字段 | 数据库字段 |
| --- | --- |
| 完成状态 | `status_raw` / `status_normalized` |
| 实际距离 | `actual_distance_km` |
| 实际用时 | `actual_duration_seconds` |
| 平均配速 | `avg_pace_seconds_per_km` |
| 平均心率 | `avg_heart_rate` |
| RPE | `rpe` |
| I 有效 km | `i_effective_km` |
| T1 有效 km | `t1_effective_km` |
| T2 有效 km | `t2_effective_km` |
| M 有效 km | `m_effective_km` |
| R 有效 km | `r_effective_km` |
| 睡眠小时 | `sleep_hours` |
| HRV | `hrv` |
| 晨脉 | `morning_heart_rate` |
| 体重 | `weight_kg` |
| 腿感 | `leg_feeling` |
| 疼痛位置 | `pain_location` |
| 疼痛等级 | `pain_level`，范围 0-5 |
| 主课数据 | `main_session_data` |
| 复盘备注 | `review_note` |
| 明日调整 | `tomorrow_adjustment` |
| 警示信息 | `alert_message` |
| 完成率 | `completion_rate` |

## 每周复盘 -> block_reviews

| Excel 字段 | 数据库字段 |
| --- | --- |
| 计划距离 | `planned_distance_km` |
| 实际距离 | `actual_distance_km` |
| 完成率 | `completion_rate` |
| I 有效 km | `i_effective_km` |
| T1 有效 km | `t1_effective_km` |
| T2 有效 km | `t2_effective_km` |
| M 有效 km | `m_effective_km` |
| R 有效 km | `r_effective_km` |
| 平均 RPE | `avg_rpe` |
| 平均体重 | `avg_weight_kg` |
| 最高疼痛等级 | `max_pain_level` |
| 复盘文字 | `review_text` |
| 下一块调整 | `next_block_adjustment` |

## 配速与规则 -> pace_rules

| Excel 字段 | 数据库字段 |
| --- | --- |
| 编码 | `code` |
| 名称 | `name` |
| 目标配速 | `target_pace_text` |
| 生理目的 | `physiological_purpose` |
| 备注 | `note` |
| 排序 | `sort_order` |

