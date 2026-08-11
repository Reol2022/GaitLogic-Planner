# Reranker

Reranker 在召回之后比较同一查询与有限候选文本的相关性。v0.16.0-D 固定使用 Dense top-8 与 BM25 top-8 的去重并集，再输出 top-4；它不搜索数据库、不会更改 Corpus，也不会参与 TODAY 的确定性决策。
