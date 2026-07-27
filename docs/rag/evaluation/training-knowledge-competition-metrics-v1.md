# Training Knowledge Competition Metrics v1

## 公共标准导出

产品仓库输出稳定 JSON，供私有竞赛仓库读取。导出只包含：

- evaluation/dataset version；
- corpus hash、index ID、provider/model；
- case ID、排名后的 chunk/document ID 和 score；
- Tool 名、reference document ID、安全错误码和验证标记；
- 聚合指标、失败 case ID、运行时间和 result hash。

不包含原始回答、Prompt、Context、Tool Result、向量、API Key、用户身份、
真实训练数据或思维链。

## 私有扩展

`gaitlogic-competition-2026` 可在不修改产品仓库的前提下扩展：

- 100–150 条私有案例；
- 多人相关性标注与一致性统计；
- embedding/provider 横向比较；
- Blind A/B；
- 真实但脱敏的用户研究；
- 竞赛图表与答辩报告。

私有仓库不得反向成为产品运行依赖，也不得把私有阈值、盲测标签或用户映射
复制回公共仓库。

## 建议图表

- 各 Baseline 的 Recall@4 / MRR@4 / nDCG@4；
- 各知识分类的召回；
- hard negative 与 abstain 表现；
- RAG citation precision/recall；
- decision invariance、warning/limitation retention；
- fallback 和 provider failure 分布；
- 失败案例类型而非用户身份分布。

## 面试表达

不要只说“做了 RAG”。应说明：如何固定数据集、如何区分检索和生成、
为什么 TODAY 决策不能由知识材料覆盖、如何用 canonical reference 防止来源
幻觉、为何需要 hard negative/abstain、如何用安全消融证明 Validator 和引用层
的独立贡献，以及哪些指标来自 fake 控制组、哪些来自真实 Provider。
