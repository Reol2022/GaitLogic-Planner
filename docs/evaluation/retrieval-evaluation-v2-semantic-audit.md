# Retrieval Evaluation v2 Semantic Audit

Labels were reviewed from query intent, document topic, and section semantics. Current Top4 was observed only after labels were authored and did not generate expected results.

- Fixture: `retrieval-fixture-2.0.0`
- Corpus: `training-knowledge-1` / `57a90da48ef857040ee88c41f1888448fd2a684c4b34268382ace153c979df0f`
- Manifest SHA-256: `29daa3f02a1e369c7c4b59a5aa4f54af343548bc72dc30813cbf2b4256de154a`
- Ranking audit: deterministic-sha256-v1, 64 dimensions, exact dense, metadata enabled, TopK=4

## ret_single_001

- Query: 高疲劳时是否应该继续高强度训练
- v1 Expected: high-fatigue-intensity-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 适用场景 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 2 | GaitLogic Training Principles | 连续增加跑量后的调整 (`progressive-volume-adjustment`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_002

- Query: 腿部沉重和疲劳时如何降低训练强度
- v1 Expected: high-fatigue-intensity-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯休整与恢复跑步的原则 (`daniels-rest-and-return-to-running`) | 判断条件 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 4 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_003

- Query: 一周内高强度课之间需要间隔多久
- v1 Expected: intensity-density-management
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季训练的阶段化思路 (`daniels-season-phasing`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_004

- Query: 如何控制质量课训练密度
- v1 Expected: intensity-density-management
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯按强度记录训练压力 (`daniels-training-stress-recording`) | 适用场景 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 推荐策略 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | Evidence | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_005

- Query: 间歇训练组间恢复应该怎样安排
- v1 Expected: interval-recovery-design
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯间歇训练（I）的有氧目的 (`daniels-interval-purpose`) | 注意事项 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_006

- Query: 间歇跑每组之间慢跑还是站立休息
- v1 Expected: interval-recovery-design
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯艰苦跑（H）与短间歇设计 (`daniels-hard-running-short-intervals`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯间歇训练（I）的有氧目的 (`daniels-interval-purpose`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯间歇训练（I）的有氧目的 (`daniels-interval-purpose`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯艰苦跑（H）与短间歇设计 (`daniels-hard-running-short-intervals`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_007

- Query: 长距离训练应该放在一周的哪一天
- v1 Expected: long-run-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 E、M、T、I、R 训练类型的目的 (`daniels-training-intensity-types`) | I：让训练与恢复共同服务最大有氧能力 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_008

- Query: 长跑前后怎样安排恢复
- v1 Expected: long-run-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 长距离训练的安排与恢复 (`long-run-placement`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 注意事项 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_009

- Query: 跑步出现疼痛时训练建议的安全边界
- v1 Expected: pain-risk-boundaries
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯间歇训练（I）的有氧目的 (`daniels-interval-purpose`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 E、M、T、I、R 训练类型的目的 (`daniels-training-intensity-types`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步机训练的适用情境 (`daniels-treadmill-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_010

- Query: 训练系统为什么不能做伤病诊断
- v1 Expected: pain-risk-boundaries
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_011

- Query: 基础期进入建设期应该注意什么
- v1 Expected: phase-transition-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 连续增加跑量后的调整 (`progressive-volume-adjustment`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 阶段二：先引入 R，避免一次加入两种新压力 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松新手与重跑者的基础建立 (`daniels-marathon-beginner-training`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_012

- Query: 训练阶段转换不能只看日期吗
- v1 Expected: phase-transition-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 训练阶段转换原则 (`phase-transition-principles`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | Evidence | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季阶段长度与周结构调整 (`daniels-phase-length-adjustment`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季阶段长度与周结构调整 (`daniels-phase-length-adjustment`) | 推荐策略 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_013

- Query: 比赛前减量期如何减少训练量
- v1 Expected: pre-race-taper-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 阶段四：把重点转向比赛所需的最后质量 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 5 公里至 10 公里训练的阶段重点 (`daniels-5k-10k-training`) | Evidence | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 1500 米至 3.2 公里训练的阶段重点 (`daniels-1500m-3200m-training`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 E、M、T、I、R 训练类型的目的 (`daniels-training-intensity-types`) | E：用轻松跑建立可持续训练量并承接恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_014

- Query: taper期间是否完全停止训练
- v1 Expected: pre-race-taper-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_015

- Query: 跑量连续增加后怎样调整
- v1 Expected: progressive-volume-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步成功要素与训练连续性 (`daniels-success-factors`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯停跑后跑量与时长的恢复调整 (`daniels-return-volume-adjustment`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_016

- Query: 周跑量增长过快后是否需要回撤
- v1 Expected: progressive-volume-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯按强度记录训练压力 (`daniels-training-stress-recording`) | 判断条件 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯按强度记录训练压力 (`daniels-training-stress-recording`) | 适用场景 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯按强度记录训练压力 (`daniels-training-stress-recording`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 4 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_017

- Query: 恢复周应该如何安排训练
- v1 Expected: recovery-week-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段二：R、T、M 内容如何共同服务半马 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯艰苦跑（H）与短间歇设计 (`daniels-hard-running-short-intervals`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_018

- Query: 恢复周是不是完全不跑步
- v1 Expected: recovery-week-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯计划内与计划外休整 (`daniels-planned-unplanned-rest`) | 注意事项 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯停跑后跑量与时长的恢复调整 (`daniels-return-volume-adjustment`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯休整与恢复跑步的原则 (`daniels-rest-and-return-to-running`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_019

- Query: 跑者力量训练一周安排几次
- v1 Expected: running-strength-basics
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步机训练的适用情境 (`daniels-treadmill-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_020

- Query: 力量训练与关键跑课如何错开
- v1 Expected: running-strength-basics
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_021

- Query: 阈值跑强度过高有哪些信号
- v1 Expected: threshold-control-signals
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯高海拔训练与比赛的考量 (`daniels-altitude-training`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯有氧能力、跑步效率与 vVO2max (`daniels-aerobic-fitness-economy`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练心率的环境边界 (`daniels-heart-rate-context`) | 适用场景 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步成功要素与训练连续性 (`daniels-success-factors`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_022

- Query: 阈值训练如何结合RPE控制
- v1 Expected: threshold-control-signals
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 核心原则 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Daniels' Running Formula | 阈值训练的周内安排 (`threshold-session-placement`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_023

- Query: 阈值课在一周中怎样安排
- v1 Expected: threshold-session-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | Daniels' Running Formula | 阈值训练的周内安排 (`threshold-session-placement`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松 2Q 计划的周结构 (`daniels-marathon-2q-plan`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_024

- Query: 阈值训练与长距离课要隔几天
- v1 Expected: threshold-session-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Daniels' Running Formula | 阈值训练的周内安排 (`threshold-session-placement`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 判断条件 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_025

- Query: 疲劳上升后如何处理原计划强度
- v1 Expected: high-fatigue-intensity-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | GaitLogic Training Principles | 高疲劳状态下的训练强度处理 (`high-fatigue-intensity-adjustment`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_026

- Query: 连续两天质量课有什么负荷风险
- v1 Expected: intensity-density-management
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_027

- Query: 比赛周前的减量应保留什么刺激
- v1 Expected: pre-race-taper-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_028

- Query: 跑步力量训练如何支持适应
- v1 Expected: running-strength-basics
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 4 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_029

- Query: 阈值课配速失控时如何判断
- v1 Expected: threshold-control-signals
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步变量、乳酸与主观用力 (`daniels-performance-variables`) | Evidence | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步变量、乳酸与主观用力 (`daniels-performance-variables`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_single_030

- Query: 长距离后的下一次质量课安排
- v1 Expected: long-run-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | Evidence | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 注意事项 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_001

- Query: 高疲劳且本周已有多次强度课怎么调整
- v1 Expected: high-fatigue-intensity-adjustment, intensity-density-management
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | GaitLogic Training Principles | 高强度训练密度管理 (`intensity-density-management`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步呼吸节奏与配速感知 (`daniels-running-breathing`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯阈值跑（T）的目的与强度感受 (`daniels-threshold-purpose`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 长距离训练的安排与恢复 (`long-run-placement`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_002

- Query: 长距离和阈值课在一周内如何错开
- v1 Expected: long-run-placement, threshold-session-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯休整与恢复跑步的原则 (`daniels-rest-and-return-to-running`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 注意事项 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 适用场景 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 长距离训练的安排与恢复 (`long-run-placement`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_003

- Query: 恢复周如何同时控制跑量和训练一致性
- v1 Expected: recovery-week-principles, progressive-volume-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 5 公里至 10 公里训练的阶段重点 (`daniels-5k-10k-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 800 米训练的阶段与速度重点 (`daniels-800m-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 5 公里至 10 公里训练的阶段重点 (`daniels-5k-10k-training`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 5 公里至 10 公里训练的阶段重点 (`daniels-5k-10k-training`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_004

- Query: 比赛前阶段转换和减量原则
- v1 Expected: pre-race-taper-principles, phase-transition-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 阶段四：把重点转向比赛所需的最后质量 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | GaitLogic Training Principles | 训练阶段转换原则 (`phase-transition-principles`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 四阶段不是固定日历，而是从重要比赛逆向设计 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_005

- Query: 阈值训练的强度与周内位置
- v1 Expected: threshold-control-signals, threshold-session-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Daniels' Running Formula | 阈值训练的周内安排 (`threshold-session-placement`) | 判断条件 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | Daniels' Running Formula | 阈值训练的周内安排 (`threshold-session-placement`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯阈值跑（T）的目的与强度感受 (`daniels-threshold-purpose`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_006

- Query: 间歇训练恢复与强度课间隔
- v1 Expected: interval-recovery-design, intensity-density-management
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松 2Q 计划的周结构 (`daniels-marathon-2q-plan`) | 推荐策略 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 推荐策略 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季训练的阶段化思路 (`daniels-season-phasing`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_007

- Query: 力量训练怎样避开长距离关键课
- v1 Expected: running-strength-basics, long-run-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季阶段长度与周结构调整 (`daniels-phase-length-adjustment`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 注意事项 | audited label comparison | audited relevance grade 1 | PARTIALLY_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 四阶段不是固定日历，而是从重要比赛逆向设计 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_008

- Query: 疲劳同时伴随疼痛时应如何保守处理
- v1 Expected: pain-risk-boundaries, high-fatigue-intensity-adjustment
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 跑者力量训练基础安排 (`running-strength-basics`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 赛期不足或伤停时，优先保留基础与最后准备 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 适用场景 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_009

- Query: 增加跑量期间如何安排恢复周
- v1 Expected: progressive-volume-adjustment, recovery-week-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 注意事项 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 适用场景 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_010

- Query: 专项期的阈值课如何循序增加
- v1 Expected: phase-transition-principles, threshold-session-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯越野跑训练的保守起步与赛季准备 (`daniels-cross-country-training`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松新手与重跑者的基础建立 (`daniels-marathon-beginner-training`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_011

- Query: 长距离后疲劳高时是否保留间歇课
- v1 Expected: long-run-placement, high-fatigue-intensity-adjustment, interval-recovery-design
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季训练的阶段化思路 (`daniels-season-phasing`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 长距离训练的安排与恢复 (`long-run-placement`) | 推荐策略 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | Public Endurance Training Guidance — GaitLogic Summary | 阈值训练中的强度控制信号 (`threshold-control-signals`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_multi_012

- Query: 减量期力量训练和跑步质量如何协调
- v1 Expected: pre-race-taper-principles, running-strength-basics
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯赛季四阶段的训练重点 (`daniels-four-season-phases`) | 阶段四：把重点转向比赛所需的最后质量 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯轻松跑（E）的目的与使用边界 (`daniels-easy-running`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松最后 18 周与 12 周准备 (`daniels-marathon-final-preparation`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 5 公里至 10 公里训练的阶段重点 (`daniels-5k-10k-training`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_001

- Query: 恢复周不是停训，应该怎样保持连续性
- v1 Expected: recovery-week-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 推荐策略 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 E、M、T、I、R 训练类型的目的 (`daniels-training-intensity-types`) | E：用轻松跑建立可持续训练量并承接恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松 4 周与 5 周周期的质量安排 (`daniels-marathon-cycles`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_002

- Query: 阈值跑不是间歇跑，强度控制看什么
- v1 Expected: threshold-control-signals
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯阈值跑（T）的目的与强度感受 (`daniels-threshold-purpose`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 3 | GaitLogic Training Principles | 连续增加跑量后的调整 (`progressive-volume-adjustment`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练心率的环境边界 (`daniels-heart-rate-context`) | Evidence | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_003

- Query: 长距离安排不是简单增加周跑量
- v1 Expected: long-run-placement
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段四：比赛期怎样降低质量负荷并安排恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | GaitLogic Training Principles | 训练阶段转换原则 (`phase-transition-principles`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯长距离跑（L）与跑量递进 (`daniels-long-run-progression`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_004

- Query: 比赛减量不是普通恢复周
- v1 Expected: pre-race-taper-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练负荷的四个变量 (`daniels-training-load-variables`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | Public Endurance Training Guidance — GaitLogic Summary | 比赛前减量原则 (`pre-race-taper-principles`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 E、M、T、I、R 训练类型的目的 (`daniels-training-intensity-types`) | E：用轻松跑建立可持续训练量并承接恢复 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯半程马拉松训练与比赛战术 (`daniels-half-marathon-training`) | 阶段三：为何由 I 或 H 强度取代 R 重点 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_005

- Query: 训练疼痛风险边界不是疲劳调整
- v1 Expected: pain-risk-boundaries
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯休整与恢复跑步的原则 (`daniels-rest-and-return-to-running`) | 判断条件 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯艰苦跑（H）与短间歇设计 (`daniels-hard-running-short-intervals`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯训练原则：个体化、适度压力与恢复 (`daniels-training-principles`) | 注意事项 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | Running Strength and Injury Prevention — GaitLogic Consensus Summary | 疼痛与伤病风险提示边界 (`pain-risk-boundaries`) | 核心原则 | audited label comparison | audited relevance grade 3 | RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_006

- Query: 阶段转换不是单周跑量波动
- v1 Expected: phase-transition-principles
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 1500 米至 3.2 公里训练的阶段重点 (`daniels-1500m-3200m-training`) | 适用场景 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松 2Q 计划的周结构 (`daniels-marathon-2q-plan`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯 800 米训练的阶段与速度重点 (`daniels-800m-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | Public Endurance Training Guidance — GaitLogic Summary | 恢复周的安排原则 (`recovery-week-principles`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_007

- Query: 力量训练安排不是跑步强度课密度
- v1 Expected: running-strength-basics
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步机训练的适用情境 (`daniels-treadmill-training`) | 核心原则 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯跑步机训练的适用情境 (`daniels-treadmill-training`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯有氧能力、跑步效率与 vVO2max (`daniels-aerobic-fitness-economy`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯停跑后跑量与时长的恢复调整 (`daniels-return-volume-adjustment`) | 判断条件 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_hard_008

- Query: 间歇组间恢复不是训练日之间间隔
- v1 Expected: interval-recovery-design
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| 1 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯巡航间歇与节奏跑的区别 (`daniels-cruise-intervals`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 2 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松新手与重跑者的基础建立 (`daniels-marathon-beginner-training`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |
| 3 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯艰苦跑（H）与短间歇设计 (`daniels-hard-running-short-intervals`) | 核心原则 | audited label comparison | audited relevance grade 2 | RELEVANT |
| 4 | 丹尼尔斯经典跑步训练法：世界最佳跑步教练的跑步公式 | 丹尼尔斯马拉松 2Q 计划的周结构 (`daniels-marathon-2q-plan`) | 推荐策略 | audited label comparison | not evidence for the audited query intent | NOT_RELEVANT |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_001

- Query: 游泳自由泳划水技术
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_002

- Query: 自行车变速器维修
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_003

- Query: 足球守门员训练
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_004

- Query: 篮球投篮动作
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_005

- Query: 请求医疗诊断处方
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_006

- Query: 查询另一个用户训练数据
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_007

- Query: 修改正式训练计划
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_008

- Query: 预测股票价格
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_009

- Query: 生成数据库密码
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。

## ret_abstain_010

- Query: 未知量子训练理论
- v1 Expected: ABSTAIN
- Current Top4:

| Rank | Source | Document | Section | Topic Match | Semantic Relevance | Decision |
|---:|---|---|---|---|---|---|
| — | — | — | — | out-of-domain | no running evidence required | RELEVANT (ABSTAIN) |

- Decision basis: 人工依据 query intent、文档主题与章节内容审查；当前排名不参与标签生成。
