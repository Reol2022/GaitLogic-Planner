# Training Knowledge RAG Evaluation v1 设计

## 目标

本评测回答两个彼此独立的问题：

1. Retriever 能否把正确的训练知识文档排进前四；
2. Coach 在引入知识材料后，能否继续保持确定性决策、引用边界和故障降级。

评测代码位于 `server/knowledge_retrieval/evaluation/`，只依赖语料、
Retriever 和 Agent 公共契约。产品运行时不导入评测模块。

## 数据流

```text
固定公开案例
  -> 严格 Schema + SHA-256
  -> Retrieval Baseline / RAG Mode
  -> 确定性断言
  -> 聚合指标
  -> 脱敏 JSON + Markdown
```

运行时临时文件放入被忽略的 `var/evaluations/`。公开结果只包含 case ID、
排名后的 chunk/document ID、分数、工具名、安全错误码、验证标记和指标。

## Retrieval 评测

公开数据集包含 60 条虚构或公开训练理论查询：

- 30 条单一明确文档；
- 12 条多相关文档；
- 8 条 hard negative；
- 10 条明确 abstain。

覆盖语料全部 12 篇文档，以及恢复、负荷管理、阈值、间歇、长距离、
周期化、减量、力量和伤病预防分类。

指标为 Hit@1/3/4、Recall@1/3/4、MRR@4、nDCG@4、过滤违规率、
禁止文档命中率、abstention precision/recall 和空结果正确率。
多相关文档按文档去重；nDCG 使用 1–3 级相关性；abstain 不进入普通召回分母。

公式：

- `Hit@k = I(top-k 至少包含一篇相关文档)`；
- `Recall@k = top-k 命中的不同相关文档数 / 全部相关文档数`；
- `MRR@4 = 1 / 前四中第一篇相关文档的排名`，未命中为 0；
- `DCG@4 = Σ(2^relevance - 1) / log2(rank + 1)`，
  `nDCG@4 = DCG@4 / IDCG@4`；
- Abstention Precision/Recall 在明确无覆盖集合上计算；
- 所有聚合值固定保留 6 位小数。

## RAG 评测

36 条案例平均覆盖 TODAY、EXPLAIN 和 GENERAL。所有 Runner State、计划、
风险和恢复信息均为固定虚构上下文。

重点硬门槛：

- 来源幻觉率、无依据声明率、规则违规率、越权修改率必须为 0；
- canonical 引用准确率、TODAY 决策不变性、警告/限制保留和 fallback
  成功率必须为 100%；
- RAG 只能提供解释材料，不能覆盖 decision、risk、planned status、
  data quality、warnings、limitations 或 canonical evidence。

## Baseline 与消融

`NO_RETRIEVAL`、`LEXICAL_ONLY`、`DENSE_NO_METADATA`、
`DENSE_WITH_METADATA` 和 `FULL_SYSTEM` 是可比较模式。BM25 仅存在于评测
包，不注册为产品 Tool。`NO_REFERENCE_MATERIALIZATION` 与
`NO_VALIDATOR_REPLAY` 明确标记 `EVALUATION_ONLY_UNSAFE_ABLATION`，不得通过
环境变量、API 或前端成为生产开关。

## 真实 Provider

真实 embedding 只能通过服务端 Settings 读取凭据，CLI 不接受 key。
公开报告不保存向量、HTTP body 或原始回答。远程模型可能变化，因此报告
记录 provider、model、index ID、语料 hash 和局限，不能声称完全可复现。

公开离线 CLI 默认不执行真实 Chat Provider。真实 RAG 需要隔离应用 Fixture、
虚构数据和显式运行流程；失败必须报错，不能回填 fake 结果。

## 质量目标

真实语义检索的项目目标为 Recall@4 ≥ 0.80、MRR@4 ≥ 0.65、
nDCG@4 ≥ 0.70、禁止文档命中率为 0。它们是项目验收目标，不是运动科学
或行业通用阈值。未达标时应调整语料、chunk、查询或 metadata，不得删除
失败案例或倒推标注。

## 当前限制

- 公开相关性标注尚未经过多人盲标；
- deterministic embedding 只验证管线和重复性，不验证语义质量；
- BM25 的中文切词采用轻量稳定近似；
- 公开 RAG 结果由 fake/offline 路径产生，不代表真实模型质量；
- 真实 Provider 延迟、用量和跨模型比较留给显式隔离评测。
