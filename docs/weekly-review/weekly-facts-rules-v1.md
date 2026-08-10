# Weekly Facts Rules v1

这些规则是产品启发式初值，不是医学阈值，也不代表竞技能力判断。

## 分类

| 状态 | 确定性条件 |
|---|---|
| `ON_TRACK` | 有有效跑步计划，且没有触发实质偏差或风险规则 |
| `UNDER_COMPLETED` | 距离完成率 `< 0.80` |
| `OVER_COMPLETED` | 距离完成率 `> 1.20` |
| `INTENSITY_IMBALANCE` | 匹配训练的计划与实际强度等级不同 |
| `RECOVERY_CONCERN` | 窗口内 Runner State 为 ELEVATED/HIGH 或风险标记大于零 |
| `INSUFFICIENT_DATA` | 没有有效跑步计划，或计划与日志均无有效事实 |
| `MIXED` | 同时满足两个或更多分类，原状态保存在 `secondary_statuses` |

`0.90–1.10` 是明确的按计划距离带；`0.80–0.90` 和 `1.10–1.20`
保留为容忍区，若没有其他偏差仍不因距离单独判为不足或超额。

## 强度和关键课

- easy：`easy`、`easy_with_speed`、`recovery`
- moderate：`long_run`、`mixed`
- hard：`interval_speed`、`tempo`
- key：`interval_speed`、`tempo`、`long_run`

长距离是关键课但不是高强度。类型来源复用产品规范化枚举，不用文本猜测。
力量训练不计入跑量。

## 完成率

```text
session_completion_rate = 已完成且匹配的计划跑步课 / 有效计划跑步课
distance_completion_rate = 有效实际跑量 / 有距离的计划跑量
key_session_completion_rate = 已完成关键课 / 计划关键课
long_run_completion_rate = 已完成长距离 / 计划长距离
```

分母为零返回 `null`。缺失实际距离不等于零；但有明确计划距离且没有任何
已完成跑步距离时，实际总量按零计算完成率。

## 偏差

支持缺课、多练、距离不足/超额、时长不足/超额、关键课缺失、长距离缺失、
强度偏高/偏低、未匹配日志、重复或歧义日志。距离和时长偏差使用 `<0.80`
及 `>1.20`。偏差包含稳定枚举、严重度、日期、内部引用、期望/实际摘要和
集中证据码。

## Runner State 趋势

至少两个历史快照才计算首尾趋势。fatigue、volume/load、recovery 和风险
分别使用有限序关系；缺少明确状态时返回 `UNKNOWN`，绝不从剩余周数、训练
文本或跑量自行推断恢复结论。

## 未来日期

窗口结束日晚于当前业务日期时，只计算截至 `as_of_date` 的事实。未来计划
不进入计划分母，也不生成缺课偏差。
