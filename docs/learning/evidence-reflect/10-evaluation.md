# Evaluation

统一评测新增 `evidence_reflect` suite，命令：

```bash
python scripts/evaluate_agent.py --suite evidence-reflect --no-write
```

公开虚构 10 案例覆盖 targeted volume/recovery acquisition、用户输入不可自动补充、重复调用跳过、no-gain、恢复冲突、RAG 边界、decision relevance、Weekly partial 和 Proposal recovery gate。

指标包括 Reflect Trigger Precision、Resolution Rate、Duplicate Tool Call Rate、Unsupported Tool Request Rate、Infinite Loop Rate、No-Gain Rate、False Ready Rate、Unsupported Decision Rate、Conflict Overclaim Rate、Blocked Domain Hallucination Rate 和 Unauthorized Plan Modification Rate。Partial 不要求强制变为 READY。
