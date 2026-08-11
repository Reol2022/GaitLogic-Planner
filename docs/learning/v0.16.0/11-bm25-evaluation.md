# BM25 Evaluation

运行 `python scripts/evaluate_bm25_retrieval.py` 会在临时目录建立 Dense 与 BM25 派生索引，使用同一公开数据集并生成 `docs/evaluation/reports/retrieval-bm25-comparison-v1.json` 与 Markdown 摘要。临时索引随运行删除，不提交向量或索引文件。

报告包含 Case Pass、Recall@4、MRR@4、nDCG@4、Forbidden Document Rate 和 Filter Violation Rate，并按 Dense-only、BM25-only、共同成功、共同失败分组。不能只看 Recall：高 Recall 仍可能把不应出现的文档排在前面，或违反 metadata filter。

17 条 Dense failure 的人工/程序辅助分类见 `docs/evaluation/retrieval-failure-analysis-v016b.md`。分类不修改 gold label；它只用于确认下一阶段应评估什么，而不是为了让基准分数更好看。
