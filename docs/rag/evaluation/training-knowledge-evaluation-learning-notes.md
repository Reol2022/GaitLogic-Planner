# Training Knowledge Evaluation 学习笔记

## 从案例到报告

入口是 `scripts/evaluate_training_knowledge.py`。CLI 先用 `datasets.py`
验证固定数据集、SHA-256、文档/工具引用，再由 `runner.py` 选择 BM25、
Dense 或 RAG 模式。`retrieval_metrics.py` 和 `rag_metrics.py` 只接收结构化
结果，最后由 `report.py` 原子写入脱敏 JSON 和 Markdown。

## 为什么检索与回答分开

Retriever 找错资料时，再好的模型也无法稳定引用；Retriever 找对后，
模型仍可能编造来源、覆盖规则或漏掉限制。因此：

- Retrieval Eval 测“找得对不对”；
- RAG Eval 测“用得对不对”；
- TODAY invariance 测“知识是否越权改变确定性事实”。

## 重要指标

Recall@4 看相关文档是否进入前四；MRR 看第一个相关结果出现多早；nDCG
利用 1–3 级相关性评价顺序。hard negative 检查相似概念混淆，abstain
检查无覆盖时能否不乱给知识。

RAG 的引用准确率必须基于 materialized canonical reference，而不是模型
自由书写的标题。unsupported claim 与 source hallucination 必须为 0；
decision invariance 必须为 1。

## 如何增加案例

1. 在对应 JSON 添加严格结构；
2. Retrieval 案例先人工阅读语料再标注；
3. RAG 案例只使用固定虚构 Fixture；
4. 更新 dataset SHA-256；
5. 运行新增专项和 CLI dry-run；
6. 检查失败报告，不要倒推标签。

## 如何增加指标

先在 per-case 结构中加入可审查的原子事实，再在 metrics 模块计算并定义
空分母语义，最后更新 reporter、测试和指标文档。不要从原始模型文本中
使用模糊 LLM Judge；v1 只使用确定性断言。

## 如何运行真实 embedding

在服务端安全环境配置 OpenAI-compatible embedding，然后显式运行：

```powershell
python scripts/evaluate_training_knowledge.py retrieval `
  --provider openai_compatible `
  --index-id <isolated-index-id>
```

CLI 没有 API Key 参数。输出不含向量或 HTTP body。远程模型会变化，
必须记录 provider/model/index/corpus，并把复现限制写入报告。

## 如何排查

- Dataset hash 错：案例内容被改动但 hash 未更新；
- Missing document：标注引用了不在 manifest 的 ID；
- Index stale：语料 root hash 与 index 不一致；
- Filter violation：检查 category/tag/language 的构造；
- nDCG 低：检查高相关文档排序；
- citation recall 低：检查 reference ID 是否经过 materialization；
- decision invariance 失败：立即视为安全阻塞，不能调整断言放行。

## 竞赛图表

把公开标准 JSON 复制到私有仓库的导入目录，在私有脚本中按 metric 和 mode
生成图表。不要让产品代码读取竞赛结果，也不要把私有案例和人工标注复制回
公开仓库。

## 项目负责人验收清单

- [ ] 数据集数量、分类和 SHA-256 正确；
- [ ] 所有 12 篇文档有覆盖；
- [ ] hard negative 与 abstain 有独立结果；
- [ ] BM25 未进入产品 Registry；
- [ ] unsafe ablation 有醒目标记；
- [ ] 报告不含原始回答、Prompt、Context、向量或 Key；
- [ ] TODAY 开关 RAG 后确定性事实不变；
- [ ] fake/deterministic 与真实 Provider 结果没有混写；
- [ ] 未达目标的真实结果被如实保留；
- [ ] Public/Private 边界通过安全脚本。
