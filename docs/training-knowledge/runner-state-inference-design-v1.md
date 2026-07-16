# 跑者状态推断规则设计 v1

> 对应版本：GaitLogic v0.10.3-B
> 文档状态：设计草案
> 规则集版本：`runner-state-rules-1.0.0-draft`
> 前置版本：v0.10.3-A Runner State Foundation

---

## 1. 设计背景

v0.10.3-A 已完成跑者状态基础数据层，能够从训练周期、训练计划、训练日志和外部同步活动中，按最近 7 天和 28 天窗口聚合训练指标。

当前系统已经可以回答：

- 跑者最近跑了多少；
- 跑了多少次；
- 训练时长是多少；
- 训练计划完成率是多少；
- RPE 和心率数据完整度如何；
- 近期完成了多少关键训练；
- 不同训练强度的距离占比如何。

但基础指标只能描述“发生了什么”，尚不能回答：

- 近期跑量是在增长、稳定还是下降；
- 训练执行是否稳定；
- 是否出现值得关注的疲劳信号；
- 是否存在连续高强度、跑量突增等训练安排问题；
- 当前状态判断基于哪些数据；
- 数据不足时系统应该如何表达不确定性。

v0.10.3-B 的目标，是在 v0.10.3-A 的确定性基础指标之上，建立一套可配置、可解释、可测试的跑者状态推断规则。

本版本不使用大语言模型进行状态判断。

---

## 2. 设计目标

本版本实现以下能力：

1. 推断近期跑量趋势；
2. 推断训练一致性；
3. 识别近期疲劳与训练压力信号；
4. 映射已有训练周期中的明确训练阶段；
5. 生成训练管理风险标记；
6. 为每个推断结果提供原因码和证据；
7. 在数据不足时返回 `UNKNOWN`；
8. 支持规则集版本管理；
9. 支持后续根据专家意见和匿名用户数据调整阈值。

本版本重点解决：

> 如何将训练统计数据转换为透明、可追溯的状态判断，而不是由系统凭感觉给跑者贴标签。

---

## 3. 非医疗声明

本模块属于训练管理和训练决策辅助模块，不提供：

- 医疗诊断；
- 伤病诊断；
- 过度训练综合征诊断；
- 康复治疗建议；
- 用药建议；
- 医疗风险预测。

系统中的 `fatigue_state` 表示：

> 基于近期跑量、RPE、计划完成情况和训练安排识别出的训练压力信号。

它不等价于医学意义上的疲劳诊断。

系统中的 `risk_flags` 表示：

> 建议跑者或教练进一步检查训练安排的管理信号。

风险标记不得使用以下措辞：

- 已受伤；
- 即将受伤；
- 过度训练；
- 危险；
- 医疗高风险；
- 必须停止运动。

推荐使用：

- 近期训练压力偏高；
- 恢复间隔可能不足；
- 建议检查近期体感；
- 建议复核后续训练安排；
- 当前数据不足，暂无法判断。

---

## 4. v0.10.3-A 可用数据

### 4.1 数据来源

当前状态模型使用以下数据实体：

- `UserAccount`
- `TrainingCycle`
- `PlannedWorkout`
- `WorkoutLog`
- `ExternalActivity`
- `WorkoutLogExternalActivity`

训练状态与训练类型使用项目现有规范化枚举：

- `WorkoutMainTypeNormalized`
- `WorkoutStatusNormalized`

### 4.2 已有基础指标

最近 7 天和 28 天分别包含：

- 训练距离；
- 训练时长；
- 训练次数；
- 完成训练次数；
- 计划训练次数；
- 计划完成率；
- 平均 RPE；
- RPE 数据覆盖率；
- 心率数据覆盖率；
- EASY 距离；
- MODERATE 距离；
- HARD 距离；
- HARD 距离比例；
- 关键课次数；
- 长距离距离；
- 距最近一次关键课的天数；
- 数据完整度；
- 数据限制说明。

### 4.3 当前数据限制

当前存在以下限制：

1. 训练周期没有结构化比赛距离字段；
2. `target_result` 为文本，仅能解析严格格式；
3. 复合训练无法可靠拆分每个强度分段的距离；
4. 强度距离暂按训练主类型归类；
5. 当前没有可靠的纵向能力表现模型；
6. 当前没有状态快照持久化；
7. 当前不能根据跑量直接判断竞技能力变化。

---

## 5. B 阶段新增派生指标

为支持状态推断，本版本需要从现有日志中派生以下指标。

### 5.1 独立基线窗口

不能直接将最近 7 天与最近 28 天平均值比较，因为最近 28 天已经包含最近 7 天，会稀释近期变化。

因此新增：

- `distance_previous_21d_km`
- `sessions_previous_21d`
- `average_rpe_previous_21d`
- `rpe_coverage_previous_21d`
- `planned_sessions_previous_21d`
- `completed_planned_sessions_previous_21d`
- `completion_rate_previous_21d`

时间窗口定义：

```text
recent_7d = 结束日及之前 6 个自然日
previous_21d = recent_7d 之前的 21 个自然日
full_28d = recent_7d + previous_21d
5.2 周级统计

新增：

active_weeks_28d
weekly_distance_breakdown_28d
weekly_session_breakdown_28d
weekly_session_mean_28d
weekly_session_cv_28d

其中：

active_week = 该自然周至少存在 1 次有效非休息训练

周训练次数变异系数：

weekly_session_cv
= weekly_session_standard_deviation
/ weekly_session_mean

当平均训练次数为 0 时，该指标返回空值。

5.3 高强度训练统计

新增：

high_intensity_sessions_7d
high_intensity_sessions_28d
consecutive_high_intensity_days_7d
maximum_consecutive_high_intensity_days_7d
6. 关键课与高强度训练的区别
6.1 关键课

关键课表示对周期训练具有重要作用的训练。

第一版包括：

间歇训练；
阈值或节奏训练；
长距离训练；
比赛或测试；
明确标记为关键训练的专项课。

关键课不等于高强度训练。

6.2 高强度训练

高强度训练表示对恢复要求较高、通常不适合连续安排的训练。

第一版包括：

间歇训练；
阈值或节奏训练；
比赛或测试；
高强度坡跑；
明确标记为高强度的专项训练。

长距离训练默认不属于高强度训练。

6.3 长距离的特殊处理

普通有氧长距离：

属于关键课
不自动属于高强度训练

包含大量马拉松配速、阈值或更高强度内容的长距离：

可以同时属于关键课和高强度训练

当前系统无法可靠拆分复合训练分段时：

不根据推测将长距离判为高强度；
按主训练类型分类；
在 limitations 中说明当前分类限制。
7. 数据充分性设计

状态推断前必须检查数据是否足够。

7.1 基础充分性条件

默认启发式参数：

minimum_valid_workouts_28d: 6
minimum_active_weeks_28d: 2
minimum_previous_21d_workouts: 3
minimum_previous_21d_active_weeks: 2
minimum_rpe_coverage: 0.50
minimum_planned_sessions_for_consistency: 4
minimum_available_fatigue_signals: 3
7.2 数据不足策略

如果以下任一条件成立：

28 天有效训练少于 6 次；
28 天活跃周少于 2 周；

则大部分推断返回：

UNKNOWN

同时输出：

INSUFFICIENT_DATA

数据不足不阻塞基础状态快照返回。

系统应继续返回：

已有基础指标；
数据质量；
缺失字段；
未执行的推断；
无法推断的原因。
8. 跑量趋势推断
8.1 命名原则

本版本推断的是：

volume_trend

不是：

load_trend

原因是当前系统主要使用跑步距离比较近期变化，尚未构建融合距离、时长、强度和主观用力程度的综合训练负荷指标。

load_trend 在本版本继续返回 UNKNOWN。

8.2 计算公式

此前 21 天周均跑量：

previous_21d_weekly_average_km
= distance_previous_21d_km / 3

近期相对基线跑量比：

volume_ratio
= distance_7d_km
/ previous_21d_weekly_average_km
8.3 状态枚举
UNKNOWN
DECREASING
STABLE
INCREASING
SPIKING
8.4 默认启发式阈值
条件	状态
volume_ratio < 0.70	DECREASING
0.70 <= volume_ratio <= 1.25	STABLE
1.25 < volume_ratio <= 1.50	INCREASING
volume_ratio > 1.50	SPIKING

这些阈值仅作为产品初始启发式参数，不作为普适运动医学标准。

8.5 UNKNOWN 条件

出现以下情况时返回 UNKNOWN：

最近 7 天距离为空；
此前 21 天距离为空；
此前 21 天周均距离为 0 或接近 0；
此前 21 天有效训练少于 3 次；
此前 21 天活跃周少于 2 周。
8.6 输出证据

示例：

{
  "state": "INCREASING",
  "reason_codes": [
    "RECENT_VOLUME_ABOVE_BASELINE"
  ],
  "evidence": [
    {
      "metric": "distance_7d_km",
      "value": 82.0,
      "window": "recent_7d"
    },
    {
      "metric": "previous_21d_weekly_average_km",
      "value": 61.0,
      "window": "previous_21d"
    },
    {
      "metric": "volume_ratio",
      "value": 1.34,
      "threshold": 1.25
    }
  ]
}
9. 训练一致性推断
9.1 状态枚举
UNKNOWN
LOW
MODERATE
HIGH
9.2 推断优先级

训练一致性优先使用计划完成数据。

当计划数据不足时，使用训练频率稳定性作为次级依据。

推断结果必须标记依据：

PLAN_COMPLETION
ACTIVITY_REGULARITY
9.3 基于计划完成率

启用条件：

planned_sessions_28d
>= minimum_planned_sessions_for_consistency

默认规则：

条件	状态
完成率 ≥ 0.85，且 4 周均活跃	HIGH
完成率 ≥ 0.60，且至少 3 周活跃	MODERATE
存在足够计划数据但未达到以上条件	LOW

计划数为 0 时：

完成率保持 null；
不得按 0 处理；
改用训练频率稳定性；
如果训练数据也不足，则返回 UNKNOWN。
9.4 基于训练频率稳定性

当计划数据不足时使用。

默认规则：

条件	状态
4 个活跃周，平均每周至少 2 次，CV ≤ 0.25	HIGH
至少 3 个活跃周，CV ≤ 0.50	MODERATE
至少 2 个活跃周但波动较大	LOW
数据不足	UNKNOWN
9.5 可信度说明

基于计划完成率的推断可信度高于基于训练频率的推断。

但第一版不输出机器学习意义上的置信概率。

可以输出：

evidence_coverage

表示推断所需证据的覆盖程度。

10. 疲劳信号状态
10.1 设计目标

fatigue_state 用于表示近期是否出现多个训练压力信号。

它不表示：

跑者已经受伤；
跑者一定恢复不足；
跑者患有过度训练综合征。
10.2 状态枚举
UNKNOWN
NORMAL
ELEVATED
HIGH
10.3 信号一：跑量增长
volume_trend == INCREASING
→ fatigue_score +1
volume_trend == SPIKING
→ fatigue_score +2
10.4 信号二：RPE 高于基线

计算：

rpe_delta
= average_rpe_7d
- average_rpe_previous_21d

该信号仅在以下条件同时满足时参与：

最近 7 天平均 RPE 存在；
此前 21 天平均 RPE 存在；
最近 7 天 RPE 覆盖率 ≥ 0.50；
此前 21 天 RPE 覆盖率 ≥ 0.50。

默认规则：

0.50 <= rpe_delta < 1.00
→ fatigue_score +1
rpe_delta >= 1.00
→ fatigue_score +2
10.5 信号三：近期计划完成率下降

计算：

completion_rate_drop
= completion_rate_previous_21d
- completion_rate_7d

仅在两个窗口均存在有效计划数据时参与。

默认规则：

completion_rate_drop >= 0.25
→ fatigue_score +1

该信号不能单独证明疲劳，只表示近期执行能力或训练安排可能出现变化。

10.6 信号四：连续高强度训练
maximum_consecutive_high_intensity_days_7d >= 2
→ fatigue_score +2

不得使用关键课次数代替高强度训练次数。

长距离不自动触发该规则。

10.7 信号五：一周高强度次数较多
high_intensity_sessions_7d >= 3
→ fatigue_score +1

该信号为提醒性质。

对于高水平跑者、双阈值训练或特殊周期，可能存在合理例外。

第一版不自动处理这些复杂例外，但应允许后续配置或人工确认。

10.8 信号六：缺少恢复日

可选规则：

最近 7 个自然日每天都有有效训练
且没有休息日
且没有明确恢复训练
→ fatigue_score +1

此规则需要明确区分：

普通轻松跑；
恢复跑；
休息日；
双练记录；
同一天多个训练日志。

如果现有数据无法可靠判断恢复训练，本规则应暂缓启用。

10.9 状态映射

默认规则：

得分	状态
0 至 1	NORMAL
2 至 3	ELEVATED
4 及以上	HIGH

只有至少 3 类疲劳信号具备有效数据时，才允许输出具体状态。

否则：

fatigue_state = UNKNOWN
10.10 输出内容

疲劳状态必须包含：

state
score
reason_codes
triggered_signals
skipped_signals
available_signal_count
total_signal_count
evidence_coverage
ruleset_version
11. 训练阶段策略
11.1 状态枚举
UNKNOWN
BASE
BUILD
SPECIFIC
PEAK
TAPER
RACE
RECOVERY
11.2 推断原则

训练阶段不根据剩余比赛周数自动推断。

只有现有训练周期存在明确结构化阶段时，才进行枚举映射。

存在明确阶段字段
→ 映射并返回
不存在明确阶段字段
→ UNKNOWN

不能仅根据以下信息猜测训练阶段：

距离比赛还有多少周；
最近跑量；
最近训练类型；
目标成绩文本；
用户近期是否参加比赛。

训练阶段将在后续训练知识模型和周期管理模块中正式结构化。

12. 风险标记
12.1 风险标记定义

第一版支持：

VOLUME_SPIKE
CONSECUTIVE_HIGH_INTENSITY_DAYS
RPE_ABOVE_BASELINE
RECENT_COMPLETION_DROP
FREQUENT_HIGH_INTENSITY_SESSIONS
12.2 严重程度
INFO
WARNING
ATTENTION

不使用医学化严重程度。

12.3 建议动作
REVIEW
REVIEW_RECOVERY
REDUCE_LOAD
ADD_RECOVERY
COLLECT_MORE_DATA
MANUAL_CONFIRMATION

本版本只生成建议动作类型，不自动修改训练计划。

12.4 风险标记结构
{
  "code": "CONSECUTIVE_HIGH_INTENSITY_DAYS",
  "severity": "ATTENTION",
  "message": "近期出现连续两天高强度训练，恢复间隔可能不足。",
  "suggested_action_type": "REVIEW_RECOVERY",
  "triggered_rule": "high_intensity_consecutive_days_v1",
  "evidence": [
    {
      "metric": "maximum_consecutive_high_intensity_days_7d",
      "value": 2,
      "threshold": 2
    }
  ]
}
12.5 数据质量问题不属于训练风险

以下内容应继续放在 data_quality 或 limitations 中：

缺少心率；
缺少 RPE；
缺少计划数据；
复合训练无法拆分；
数据量不足。

不能把“用户没有填写 RPE”描述为训练风险。

13. UNKNOWN 策略

以下情况应优先返回 UNKNOWN：

样本数量不足；
基线窗口为空；
关键字段缺失；
数据覆盖率不足；
推断所需信号少于最低数量；
当前数据模型无法表达所需概念；
规则存在明显歧义；
结论只能通过猜测产生。

UNKNOWN 不代表系统失败。

它表示：

当前数据不足以支持可靠判断。

输出 UNKNOWN 时，应同时说明：

缺少哪些数据；
哪些规则没有执行；
用户需要补充什么；
是否仍可返回基础指标。
14. Evidence 与 Reason Code
14.1 Reason Code

Reason Code 用于说明系统为什么产生该结论。

示例：

RECENT_VOLUME_BELOW_BASELINE
RECENT_VOLUME_STABLE
RECENT_VOLUME_ABOVE_BASELINE
RECENT_VOLUME_SPIKE
HIGH_PLAN_COMPLETION
MODERATE_PLAN_COMPLETION
LOW_PLAN_COMPLETION
STABLE_ACTIVITY_FREQUENCY
UNSTABLE_ACTIVITY_FREQUENCY
RPE_ABOVE_BASELINE
RECENT_COMPLETION_DROP
CONSECUTIVE_HIGH_INTENSITY_DAYS
FREQUENT_HIGH_INTENSITY_SESSIONS
INSUFFICIENT_BASELINE_DATA
INSUFFICIENT_RPE_COVERAGE
INSUFFICIENT_PLAN_DATA
INSUFFICIENT_FATIGUE_SIGNALS
14.2 Evidence

每条证据至少包含：

指标名称；
实际值；
比较窗口；
阈值；
单位；
数据来源；
是否参与推断。

示例：

{
  "metric": "rpe_delta",
  "value": 1.2,
  "threshold": 1.0,
  "unit": "rpe",
  "window": "recent_7d_vs_previous_21d",
  "source": "workout_logs",
  "used": true
}
14.3 可解释性原则

系统不允许只返回：

疲劳状态：HIGH

必须能够回答：

哪些信号触发了判断；
哪些信号因数据不足没有参与；
每个信号贡献了多少分；
使用了哪一个规则集版本；
数据窗口截止日期是什么。
15. 统一推断结果结构

建议使用统一结构：

{
  "state": "ELEVATED",
  "score": 3,
  "reason_codes": [
    "RECENT_VOLUME_ABOVE_BASELINE",
    "RPE_ABOVE_BASELINE"
  ],
  "evidence": [],
  "available_signal_count": 4,
  "total_signal_count": 5,
  "evidence_coverage": 0.8,
  "ruleset_version": "runner-state-rules-1.0.0"
}

其中：

evidence_coverage
= available_signal_count / total_signal_count

该值只表示证据覆盖程度，不表示状态预测准确率。

16. 默认启发式参数
version: "runner-state-rules-1.0.0"

data_sufficiency:
  minimum_valid_workouts_28d: 6
  minimum_active_weeks_28d: 2
  minimum_previous_21d_workouts: 3
  minimum_previous_21d_active_weeks: 2
  minimum_rpe_coverage: 0.50
  minimum_planned_sessions_for_consistency: 4
  minimum_available_fatigue_signals: 3

volume_trend:
  decreasing_below: 0.70
  stable_upper: 1.25
  increasing_upper: 1.50

consistency:
  high_completion_rate: 0.85
  moderate_completion_rate: 0.60
  high_active_weeks: 4
  moderate_active_weeks: 3
  high_weekly_session_cv: 0.25
  moderate_weekly_session_cv: 0.50
  minimum_average_sessions_per_week_for_high: 2.0

fatigue:
  rpe_delta_moderate: 0.50
  rpe_delta_high: 1.00
  completion_rate_drop: 0.25
  frequent_high_intensity_sessions: 3
  consecutive_high_intensity_days: 2
  elevated_score: 2
  high_score: 4

所有参数必须集中配置，不得散落在业务代码中。

17. 规则优先级

状态推断建议采用以下顺序：

1. 读取基础状态快照
2. 检查数据充分性
3. 计算独立基线窗口
4. 推断跑量趋势
5. 推断训练一致性
6. 计算疲劳信号
7. 生成疲劳状态
8. 映射训练阶段
9. 生成风险标记
10. 汇总 evidence、reason codes 和 limitations

风险标记应基于已经计算完成的基础指标和推断结果，不重复实现同一公式。

18. 暂不推断的状态
18.1 综合负荷趋势
load_trend = UNKNOWN

原因：

当前没有统一训练负荷分数；
跑量无法完整代表训练压力；
不同强度下相同距离的负荷不同；
复合训练无法精确拆分分段强度。

后续应单独设计：

session-RPE 负荷；
时长 × RPE；
TRIMP 或其他心率负荷；
多指标融合负荷。
18.2 能力状态
fitness_state = UNKNOWN

不能通过跑量或完成率直接判断竞技能力。

能力状态需要：

比赛成绩趋势；
标准测试趋势；
VDOT 变化；
相似训练下的配速变化；
相似配速下的心率变化；
关键课表现变化。
18.3 能力短板
weaknesses = []

不能仅根据训练类型占比推断能力短板。

短板分析需要独立的能力模型和专项评测规则。

19. 例外情况
19.1 比赛周

比赛可能导致：

高强度次数增加；
跑量下降；
RPE升高；
完成率变化。

如果已有明确比赛标记，后续可以为比赛周建立例外规则。

第一版如果无法可靠识别比赛周：

不自动豁免；
在 evidence 中保留训练类型；
允许人工复核。
19.2 双阈值训练

高水平跑者可能在一天内安排两次阈值训练。

如果两次训练发生在同一天：

不应计为连续两个自然日；
可以计入高强度训练次数；
后续需要单独分析单日负荷。
19.3 高跑量跑者

高跑量跑者连续多天训练并不一定代表恢复不足。

因此“无休息日”规则不能单独触发高疲劳状态，只能作为低权重信号。

19.4 恢复跑

恢复跑与普通轻松跑可能使用相同主类型。

在系统没有明确恢复跑标记前，不应假设所有轻松跑都是恢复训练。

20. 后续校准方法

默认阈值上线前应经过：

项目负责人训练经验审查；
典型虚构案例测试；
极端边界案例测试；
小范围跑友灰度测试；
用户对状态判断的反馈；
专业跑者或教练审核；
匿名内测数据统计。

校准过程中必须区分：

产品启发式调整；
用户偏好调整；
专家意见；
数据统计结果；
医学或科研结论。

不得通过少量内测数据宣称形成普适训练科学标准。

21. 开源边界
21.1 适合进入公开产品仓库
状态推断框架；
默认启发式规则；
规则配置结构；
Reason Code；
Evidence 数据结构；
风险标记结构；
单元测试；
虚构测试案例；
技术文档。
21.2 保持在私有竞赛仓库
真实用户状态快照；
用户问卷原始回答；
根据真实用户调优后的私有参数；
比赛对照实验结果；
用户访谈；
竞赛报告；
答辩材料。
21.3 两个仓库都不得保存
Garmin Token；
API Key；
数据库密码；
生产数据库；
未脱敏训练记录；
用户身份映射；
手机号和邮箱；
原始问卷数据。
22. 验收标准

v0.10.3-B 实现完成后，应满足：

跑量趋势使用最近 7 天和此前 21 天独立比较；
不将跑量趋势命名为综合负荷趋势；
长距离不自动视为高强度训练；
计划数为 0 时完成率保持空值；
RPE覆盖率不足时不触发RPE规则；
疲劳状态至少需要 3 类有效信号；
每个状态都有 Evidence；
每个状态都有 Reason Code；
阈值集中在版本化配置文件中；
数据不足时返回 UNKNOWN；
fitness_state 保持 UNKNOWN；
weaknesses 保持空列表；
load_trend 保持 UNKNOWN；
不输出医学诊断；
不自动调整训练计划；
相同输入产生相同输出；
不调用大语言模型；
不修改训练数据；
不创建数据库迁移；
所有测试使用虚构数据。
23. 待项目负责人确认

在进入开发前，需要最终确认：

跑量趋势阈值是否采用：
0.70
1.25
1.50
RPE变化是否采用：
增加 0.50 记 1 分
增加 1.00 记 2 分
高强度训练一周达到 3 次是否记 1 分；
连续 2 个自然日高强度是否记 2 分；
疲劳状态分数是否采用：
0至1：NORMAL
2至3：ELEVATED
4及以上：HIGH
是否在第一版启用“最近 7 天无恢复日”规则；
阈值是否公开，还是只公开框架并将后续调优参数保持私有；
节奏跑是否全部归入高强度，还是需要区分稳态跑、马拉松配速跑和阈值跑。
24. 设计结论

v0.10.3-B 不负责判断跑者是否“变强了”，也不负责自动修改训练计划。

它的职责是：

在已有训练数据基础上，识别近期跑量变化、训练执行稳定性和训练压力信号，并通过可追溯证据解释判断过程。

本版本输出将作为后续模块的输入：

训练计划校验；
训练规则引擎；
动态调整；
训练决策智能体；
用户状态展示；
竞赛评测体系。

状态推断必须保持保守、透明和可复现。

当系统没有足够证据时，正确答案是 UNKNOWN，而不是生成一个听起来很专业的猜测。
