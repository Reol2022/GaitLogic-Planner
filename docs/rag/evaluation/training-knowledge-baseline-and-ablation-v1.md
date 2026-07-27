# Training Knowledge Baseline and Ablation v1

## Baseline

| 模式 | 目的 | 生产路径 |
| --- | --- | --- |
| NO_RETRIEVAL | 测量完全没有知识材料时的差异 | 否 |
| LEXICAL_ONLY | 轻量 BM25 基线 | 否 |
| DENSE_NO_METADATA | 测量纯向量检索 | 仅评测组合 |
| DENSE_WITH_METADATA | 测量分类/标签过滤贡献 | 是 |
| FULL_SYSTEM | 工具、规则、检索、引用、Validator、Fallback | 是 |

BM25 使用稳定的英文 token 和中文二元近似切词，分数相同时按 chunk ID 排序。
它不引入大型依赖，不加入 Tool Registry，也不会替换正式 Retriever。

`deterministic_test` embedding 仅控制重复性。它的召回分数不能作为语义模型
质量证据，报告必须明确标识。

## Ablation

`NO_REFERENCE_MATERIALIZATION` 移除 canonical reference materialization；
`NO_VALIDATOR_REPLAY` 跳过离线 Validator 重放。二者只用于说明安全层贡献，
必须携带 `EVALUATION_ONLY_UNSAFE_ABLATION` 标记。

禁止实现以下生产开关：

- API 请求选择跳过 Validator；
- 环境变量关闭引用校验；
- 前端选择 raw Tool Result；
- Provider 自行覆盖 TODAY 确定性事实。

## 解释结果

比较时使用同一数据集版本、语料 hash、index 和 top-k。不能把不同 Provider、
不同 corpus 或不同 filters 的结果直接归因于某一层。

真实 Dense 目标为 Recall@4 ≥ 0.80、MRR@4 ≥ 0.65、nDCG@4 ≥ 0.70。
若未达标，优先检查：

1. 文档边界与 chunk section；
2. 查询是否需要 metadata；
3. embedding 模型语言能力；
4. hard negative 是否暴露文档重叠；
5. 语料是否缺少明确覆盖。

不得通过降低阈值、删失败案例或把不相关文档改为相关来“优化”分数。
